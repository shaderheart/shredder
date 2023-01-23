from hashlib import new
import traceback
import bpy
from mathutils import *
import math
import idprop
import mathutils

from dataclasses import dataclass, field, asdict
from enum import IntEnum
import json

from .shred_component import ShredAssets, shredCameraComponent, shredPhysicsShape
from .material_baker import process_material

_DEBUG_PRINT = False

class shPhysicsShape(IntEnum):
    BOX = 0
    SPHERE = 1
    CAPSULE = 2
    MESH = 3
    HEIGHTMAP = 4
    COMPOUND = 5
    CONVEX = 6

    def get(val):
        if val == "BOX":
            return shPhysicsShape.BOX
        elif val == "SPHERE":
            return shPhysicsShape.SPHERE
        elif val == "CAPSULE":
            return shPhysicsShape.CAPSULE
        elif val == "MESH":
            return shPhysicsShape.MESH
        elif val == "CONVEX_HULL":
            return shPhysicsShape.CONVEX

        if val == shredPhysicsShape.BOX:
            return shPhysicsShape.BOX
        elif val == shredPhysicsShape.SPHERE:
            return shPhysicsShape.SPHERE
        elif val == shredPhysicsShape.CAPSULE:
            return shPhysicsShape.CAPSULE
        elif val == shredPhysicsShape.MESH:
            return shPhysicsShape.MESH
        elif val == shredPhysicsShape.CONVEX_HULL:
            return shPhysicsShape.CONVEX

        return shPhysicsShape.BOX


@dataclass
class shPhysics:
    shape: shPhysicsShape = shPhysicsShape.BOX
    is_static: bool = False
    is_kinematic: bool = False
    is_trigger: bool = False
    origin: list[float] = field(default_factory=lambda: [0, 0, 0])
    scale: list[float] = field(default_factory=lambda: [1, 1, 1])
    box_extents: list[float] = field(default_factory=lambda: [1, 1, 1])
    height: float = 1
    radius: float = 1
    mass: float = 1
    bounce: float = 1
    friction: float = 1
    linear_damping: float = 1
    angular_damping: float = 1
    belongs: int = 0x0FFFFFFF
    responds: int = 0x0FFFFFFF


@dataclass
class shCharacterController:
    radius: float = 0.5
    height: float = 2.0
    displacement: list[float] = field(default_factory=lambda: [0, 0, 0])


def duplicate_hierarcy(parent_object, collection, new_parent):
    for child in parent_object.children:
        new_child = bpy.data.objects.new(child.name, child.data)
        new_child.matrix_world = child.matrix_world
        new_child.parent = new_parent
        new_child.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        if parent_object.get("shredder", "") != "":
            clone_shredder_properties(child, new_child)
        collection.objects.link(new_child)
        duplicate_hierarcy(child, collection, new_child)

def clone_property(into, property):
    if property is not None:
        for key, item in property.items():
            if not isinstance(item, idprop.types.IDPropertyGroup):
                if isinstance(item, idprop.types.IDPropertyArray):
                    for index, subitem in enumerate(item):
                        exec(f"into.{key}[index] = subitem")
                else:
                    try:
                        exec(f"into.{key} = property.{key}")
                    except:
                        print(traceback.format_exc())
            else:
                exec(f"clone_property(into.{key}, property.{key})")


def clone_shredder_properties(from_object, into_object):
    if from_object.get("shredder", "") != "":
        for key, item in from_object.shredder.items():
            try:
                exec(f"clone_property(into_object.shredder.{key}, from_object.shredder.{key})")
            except Exception:
                print(traceback.format_exc())
                print(f"failed to insert property: {key}")


def realize_evaluated_nodes(forObject):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evalA = forObject.evaluated_get(depsgraph)
    collection = bpy.data.collections.new(forObject.name + '_EVAL')
    bpy.context.scene.collection.children.link(collection)
    layer_collection = bpy.context.view_layer.layer_collection.children[collection.name]
    bpy.context.view_layer.active_layer_collection = layer_collection

    for inst in depsgraph.object_instances:
        if inst.parent == evalA and inst.is_instance and inst.instance_object.name != inst.parent.name:
            real_object = bpy.data.objects[inst.instance_object.name]
            if real_object.parent is None:
                # new_object = bpy.data.objects.new(
                #     real_object.name, real_object.data)
                new_object = real_object.copy()
                new_object.matrix_world = inst.matrix_world
                clone_shredder_properties(real_object, new_object)
                collection.objects.link(new_object)
                duplicate_hierarcy(real_object, collection, new_object)


def buildComponentPropDict(object, component_name, component_params, properties, recursed=False, parent_name=""):
    for key in properties:
        if isinstance(properties[key], dict):
            buildComponentPropDict(
                object, key, component_params, properties[key], True, component_name)
        else:
            if not recursed:
                exec(f'properties[key] = type(properties[key])(object.shredder.{component_name}.{key})')
            else:
                exec(
                    f'properties[key] = type(properties[key])(object.shredder.{parent_name}.{component_name}.{key})')


def shredPreSave(var1, var2):
    D = bpy.data
    C = bpy.context

    bpy.ops.ed.undo_push()

    # get extra light parameters
    for light in D.lights:
        if "cycles" in light and "cast_shadow" in light.cycles:
            light["shred_shadows_enabled"] = light.cycles.cast_shadow

    original_material_list = []
    for material in D.materials:
        original_material_list.append(material)

    # bake materials if necessary
    baked_material_list = []
    for material in original_material_list:
        force_rebake = False
        if "shred_force_rebake" in bpy.context.scene:
            force_rebake = int(bpy.context.scene.shred_force_rebake)
        baked_or_none = process_material(material, force_rebake=force_rebake)
        if baked_or_none is not None:
            baked_material_list.append(baked_or_none)

    camera_count = 0

    for object in D.objects:
        pythonized = {}

        # replace bakeable materials with the baked versions
        for idx, material_slot in enumerate(object.material_slots):
            if material_slot.material is not None and "baked_version" in material_slot.material:
                object.material_slots[idx].material = bpy.data.materials[material_slot.material["baked_version"]]

        if object.type == "CAMERA":
            camera = {
                "zFar": object.data.clip_end,
                "zNear": object.data.clip_start,
                "FOV": object.data.angle * 180 / math.pi,
                "active": camera_count == 0,
            }

            pythonized["camera"] = camera
            camera_count += 1

        if object.type == "LIGHT":
            light = {
                "castShadows": object.data.use_shadow,
                "shadowQuality": 512,
            }
            pythonized["light"] = light

        for collection in object.users_collection:
            if collection.name == ("prototypes"):
                pythonized["prototype"] = True
                break

        if object.animation_data is not None:
            print("Object has animation!")
            pythonized["animation_list"] = []
            for key, value in object.animation_data.nla_tracks.items():
                print(f'Found animation: {key}')
                pythonized["animation_list"].append(key)

        if "script" in object and object["script"] != "":
            print("has a script! checking for variables.")
            pythonized["script"] = object["script"]
            pythonized["scriptvars"] = {}
            scriptvars = []
            for proper in object.keys():
                if "scriptvar_" in proper:
                    scriptvars.append(proper)

            for scriptvar in scriptvars:
                title = scriptvar.replace("scriptvar_", "")
                pythonized["scriptvars"][title] = object[scriptvar]
            print(pythonized["scriptvars"])

        if "shredder" in object:
            for component, cvalue in object["shredder"].items():
                properties = {}
                if component in ShredAssets.componentPropMap:
                    properties = asdict(
                        ShredAssets.componentPropMap[component])
                elif component in ShredAssets.ecomponentPropMap:
                    properties = (ShredAssets.ecomponentPropMap[component])

                component_params = object.shredder[component]

                if component != "physics":
                    buildComponentPropDict(
                        object, component, component_params, properties)
                    # for key, value in component_params.items():
                    # 	exec(f'properties[key] = type(properties[key])(object.shred_{component}.{key})')

                    if component == "script":
                        scriptvars = []
                        properties["scriptvars"] = {}
                        for proper in object.keys():
                            if "scriptvar_" in proper:
                                scriptvars.append(proper)

                        for scriptvar in scriptvars:
                            title = scriptvar.replace("scriptvar_", "")
                            if isinstance(object[scriptvar], idprop.types.IDPropertyArray):
                                properties["scriptvars"][title] = object[scriptvar].to_list(
                                )
                            else:
                                properties["scriptvars"][title] = object[scriptvar]
                    if _DEBUG_PRINT:
                        print(properties)
                    pythonized[component] = properties

                else:
                    body = shPhysics()
                    body.scale[0] = object.scale[0]
                    body.scale[1] = object.scale[1]
                    body.scale[2] = object.scale[2]
                    body.friction = float(object.shredder.physics.friction)
                    body.bounce = float(object.shredder.physics.bounciness)
                    body.mass = float(object.shredder.physics.mass)
                    body.linear_damping = float(
                        object.shredder.physics.angular_damping)
                    body.angular_damping = float(
                        object.shredder.physics.linear_damping)
                    body.is_static = int(object.shredder.physics.static)
                    body.is_kinematic = int(object.shredder.physics.kinematic)
                    body.is_trigger = int(object.shredder.physics.trigger)
                    body.box_extents[0] = object.dimensions[0]
                    body.box_extents[1] = object.dimensions[2]
                    body.box_extents[2] = object.dimensions[1]
                    body.box_extents[0] /= body.scale[0]
                    body.box_extents[1] /= body.scale[1]
                    body.box_extents[2] /= body.scale[2]
                    body.radius = body.box_extents[0]
                    body.height = body.box_extents[1]
                    body.shape = shPhysicsShape.get(
                        object.shredder.physics.shape)

                    belongs = 0
                    boolIndex = 0
                    for belongsBool in object.shredder.physics.belongs:
                        belongs = belongs | (belongsBool << boolIndex)
                        boolIndex += 1
                    body.belongs = belongs

                    responds = 0
                    boolIndex = 0
                    for respondsBool in object.shredder.physics.responds:
                        responds = responds | (respondsBool << boolIndex)
                        boolIndex += 1
                    body.responds = responds
                    # body.shape = shPhysicsShape.get(object.rigid_body.collision_shape)
                    pythonized["physics"] = asdict(body)

        # if the object does not get rendered on Blender, shred should not render it either
        if object.hide_render:
            pythonized['dont_render'] = True
        object["shred"] = json.dumps(pythonized)
        if _DEBUG_PRINT:
            print(object["shred"])
