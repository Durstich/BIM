# Import clr and RevitServices
# -*- coding: utf-8 -*-
import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitServices')
from Autodesk.Revit.DB import *
from RevitServices.Persistence import *
from RevitServices.Transactions import *

# 0.1. Get the current document, view and name
doc = __revit__.ActiveUIDocument.Document 
uidoc = __revit__.ActiveUIDocument
view = doc.ActiveView.Id

# 0.2. Define functions used in the script

def collect_and_union_room_boundaries(rooms):
    boundaries = []
    options = SpatialElementBoundaryOptions()
    
    for room in rooms:
        room_boundaries = room.GetBoundarySegments(options)
        room_boundary_curves = []
        
        for boundary_list in room_boundaries:
            for boundary_segment in boundary_list:
                curve = boundary_segment.GetCurve()
                room_boundary_curves.append(curve)
        
        boundaries.append(room_boundary_curves)

    # Union the collected boundaries
    union_boundaries = []
    for boundary_curves in boundaries:
        curve_loop = CurveLoop()
        for curve in boundary_curves:
            curve_loop.Append(curve)
        union_boundaries.append(curve_loop)
        print("Unioned boundary curves: ", len(curve_loop))
    
    return union_boundaries

def create_floors_from_boundaries(doc, union_boundaries, floor_type_id, floor_level_id):
    
    with Transaction(doc, "Create Floors") as t:
        t.Start()
        
        for boundary in union_boundaries:
            curve_array = CurveArray()
            for curve in boundary:
                curve_array.Append(curve)
            
            new_floor = Floor.Create(doc,curve_array, floor_type_id, floor_level_id)
            print("Created floor with area: ", new_floor.LookupParameter("Area").AsDouble())
        
        t.Commit()

def create_ceilings_from_boundaries(doc, union_boundaries, ceiling_type_id, ceiling_level_id):
    
    with Transaction(doc, "Create Floors") as t:
        t.Start()
        
        for boundary in union_boundaries:
            curve_array = CurveArray()
            for curve in boundary:
                curve_array.Append(curve)
            
            new_ceiling = Floor.Create(doc,curve_array, ceiling_type_id, ceiling_level_id)
            print("Created floor with area: ", new_ceiling.LookupParameter("Area").AsDouble())

            # Set the Height Offset From Level parameter to 0
            height_offset_param = new_ceiling.get_Parameter(BuiltInParameter.CEILING_HEIGHTABOVELEVEL_PARAM)
            if height_offset_param:
                height_offset_param.Set(0)
        
        t.Commit()



# 1.1. Get level and floor/ceiling collectors.
base_level_name = "Level 0"
ceiling_level_name = "Sales area walls"
floor_family_collector = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Floors).WhereElementIsElementType().ToElements()
ceiling_family_collector = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Ceilings).WhereElementIsElementType().ToElements()

# 1.2. Get the Id of the level with the name ceiling_level_name
levels_collector = FilteredElementCollector(doc).OfClass(Level)
ceiling_level_id = None
base_level_id = None
for level in levels_collector:
    if level.Name == ceiling_level_name:
        ceiling_level_id = level.Id
    if level.Name == base_level_name:
        base_level_id = level.Id

if ceiling_level_id:
    print("Ceiling level ", ceiling_level_name, "found with ID:", ceiling_level_id)
else:
    print("Ceiling level ", ceiling_level_name, "not found")

if base_level_id:
    print("Base level ", base_level_name, "found with ID:", base_level_id)
else:
    print("Base level ", base_level_name, "not found")



# 2. Get RD_ScopeBox and its boundingbox
scope_box_name = "RD_ScopeBox"
collector = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_VolumeOfInterest).WhereElementIsNotElementType()
scope_box = None

for element in collector:
    if element.Name == scope_box_name:
        scope_box = element
        break

if scope_box:
    print("Scope box ",scope_box_name,"found with ID:",scope_box.Id)
    bounding_box = scope_box.get_BoundingBox(doc.ActiveView)
    if bounding_box:
        print("Bounding Box Min:", bounding_box.Min)
        print("Bounding Box Max:", bounding_box.Max)
else:
    print("Scope box",scope_box_name, "not found")

# 3. Get all rooms in the project
rooms_collector = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).WhereElementIsNotElementType()
rooms = [room for room in rooms_collector]

print("Total number of rooms: ", len(rooms))
for room in rooms:
    room_name = room.LookupParameter("Name").AsString()
    #print("Room Name: ", room_name, ", Room ID: ", room.Id)

# 4. Get rooms inside the scope box
rooms_inside_scope_box = []
for room in rooms:
    room_location = room.Location
    if isinstance(room_location, LocationPoint):
        room_point = room_location.Point
        if (bounding_box.Min.X <= room_point.X <= bounding_box.Max.X and
            bounding_box.Min.Y <= room_point.Y <= bounding_box.Max.Y and
            bounding_box.Min.Z <= room_point.Z <= bounding_box.Max.Z):
            rooms_inside_scope_box.append(room)

print("Total number of rooms inside scope box: ", len(rooms_inside_scope_box))
for room in rooms_inside_scope_box:
    room_name = room.LookupParameter("Name").AsString()
    room_area = room.LookupParameter("Area").AsDouble() * 0.092903  # Convert square feet to square meters
    print("     Room Name: ", room_name,",           Room Area (m²): ", room_area)
    
    
    





    
# 5.1. Get the backroom area rooms and its geometry projection at level 0.
backroom_area_names = ["BACKUP FACILITIES", "COMMON AREA", "TOILETS"]
backroom_area_rooms = [backroom for backroom in rooms_inside_scope_box if backroom.LookupParameter("Name").AsString() in backroom_area_names and backroom.Location is not None]
backrooms_gtry_options = Options()
backroom_area_rooms_unionspace_2D = None

backroom_room_projection = collect_and_union_room_boundaries(backroom_area_rooms)

# 6.1. Get the sales area rooms and its geometry projection at level 0. 
sales_area_rooms = [salesroom for salesroom in rooms_inside_scope_box if salesroom not in backroom_area_rooms and salesroom.Location is not None]
salesrooms_gtry_options = Options()
sales_area_rooms_unionspace_2D = None


sales_room_projection = collect_and_union_room_boundaries(sales_area_rooms)


# 7.1. Get the wet/utility area rooms and its geometry projection at level 0 - only for ceilings.
wet_area_names = ["TOILETS"]
wet_area_rooms = [wetroom for wetroom in backroom_area_rooms if wetroom.LookupParameter("Name").AsString() in wet_area_names and wetroom.Location is not None]
wetrooms_gtry_options = Options()
wet_area_rooms_unionspace_2D = None


wet_room_projection = collect_and_union_room_boundaries(wet_area_rooms)

# 8.1. Get the shopfront area rooms and its geometry projection at level 0 - only for ceilings.
shopfront_area_names = ("SHOP WINDOW")
shopfront_area_rooms = [frontroom for frontroom in sales_area_rooms if frontroom.LookupParameter("Name").AsString() in shopfront_area_names and frontroom.Location is not None]
shopfront_gtry_options = Options()
shopfront_area_rooms_unionspace_2D = None


shopfront_room_projection = collect_and_union_room_boundaries(shopfront_area_rooms)









# 8. Get the salesarea floor type.
salesarea_floor_name = "S18_M0402_sale's area"
salesarea_floor_type = [f for f in floor_family_collector if f.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM).AsString() == salesarea_floor_name]
print("Sales Area Floor Type: ", salesarea_floor_type)

# 9. Get the backroom floor type.
backroom_floor_name = "S18_M0414_backup facilities"
backroom_floor_type = [f for f in floor_family_collector if f.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM).AsString() == backroom_floor_name]
print("Backroom Floor Type: ", backroom_floor_type)

# 10. Get the wet/utility area ceiling type.
backroom_ceiling_name = "S18_Backroom"
backroom_ceiling_type = [f for f in ceiling_family_collector if f.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM).AsString() == backroom_ceiling_name]
print("Backroom Ceiling Type: ", backroom_ceiling_type)

# 11. Get shopfront area ceiling type.
shopfront_ceiling_name = "S18_Shopfront"
shopfront_ceiling_type = [f for f in ceiling_family_collector if f.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM).AsString() == shopfront_ceiling_name]
print("Shopfront Ceiling Type: ", shopfront_ceiling_type)





# 12.1. Create sales area floor.
new_salesarea_floor = create_floors_from_boundaries(doc, sales_area_rooms_unionspace_2D, salesarea_floor_type[0].Id, base_level_id)

# 12.2. Create backroom floor.
new_backroom_floor = create_floors_from_boundaries(doc, backroom_area_rooms_unionspace_2D, backroom_floor_type[0].Id, base_level_id)

# 12.3. Create wet/utility area ceiling.
new_wetarea_ceiling = create_ceilings_from_boundaries(doc, wet_area_rooms_unionspace_2D, backroom_ceiling_type[0].Id, ceiling_level_id)

# 12.4. Create shopfront area ceiling.
new_shopfront_ceiling = create_ceilings_from_boundaries(doc, shopfront_area_rooms_unionspace_2D, shopfront_ceiling_type[0].Id, ceiling_level_id)


