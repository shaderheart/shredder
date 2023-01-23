from multiprocessing.shared_memory import ShareableList
from time import sleep
import os
import platform
from unicodedata import name 

import bpy
from bpy.types import PropertyGroup
from bpy.app.handlers import persistent
import nodeitems_utils
import mathutils



from . import physicsData, material_baker
from .shred_component import (ShredAssets, loadShredScripts, loadShredComponents,
    buildComponentProperties, injectComponentProperties, clearComponentProperties, getComponentProperties, draw_component_props)
from .material_extensions import ShaderNodeShredVideoTexture, ShredShaderNodeCategory, shred_node_categories
from .gpu_tools import ApplyLightningBake

path_delimiter = "\\" if (platform.system == "Windows") else "/"

def walk_shred_package():
    blend_file_directory = bpy.path.abspath(f"//")
    print(blend_file_directory)
    shred_package = blend_file_directory.find("package")
    print(shred_package)

    shred_package_directory = blend_file_directory + "../"

    asset_type_list = ['music', 'midis', 'soundEffects', 'impulses', 'videos', 'particles']

    for asset_type in asset_type_list:
        ShredAssets.file_assets[asset_type].clear()
        direct = shred_package_directory + asset_type
        print(direct)
        for base, fdirs, fnames in os.walk(direct):
            relative_base = base.replace(direct, '')
            for fname in fnames:
                relative_file = relative_base + "/" + fname if relative_base != "" else fname
                extension_location = relative_file.rfind(".")
                if extension_location > 0:
                    relative_file = relative_file[:extension_location]
                print(relative_file)

                ShredAssets.file_assets[asset_type][relative_file] = f'{relative_file}'
                print(f'{asset_type}: {relative_base}:{fname}')

shred_gltf_export_completed = False

def shred_export_gltf(filename):
    targetFolder = filename
    targetFolderSeparator = filename.rfind("/")
    if targetFolderSeparator != 0:
        targetFolder = targetFolder[:targetFolderSeparator]
        if not os.path.exists(targetFolder):
            os.makedirs(targetFolder)

    bpy.ops.export_scene.gltf(filepath=filename, convert_lighting_mode='COMPAT', export_format='GLTF_SEPARATE', export_texture_dir='tex', check_existing=False, use_active_scene=True,
     export_cameras=True, export_extras=True, export_apply=True, export_all_influences=True, export_lights=True, will_save_settings=True, use_mesh_edges=True, export_def_bones=True, export_current_frame=False)


@persistent
def shred_save_handler(var1):
    physicsData.shredPreSave(None, None)

@persistent
def shred_export_undoer():
    global shred_gltf_export_completed
    if shred_gltf_export_completed:
        print("Initiating undoer!")
        # bpy.ops.ed.undo()
        bpy.ops.wm.revert_mainfile()
        shred_gltf_export_completed = False
    return 2.0


def register():
    ShredAssets.register_object_props()
    bpy.types.Scene.shred_bake_quality = bpy.props.EnumProperty(items=[
        ("256", "Scratch", "Scratch"),
        ("512", "Low", "Low"),
        ("1024", "Medium", "Medium"),
        ("2048", "High", "High"),
    ])
    bpy.types.Scene.shred_force_rebake = bpy.props.BoolProperty()
    bpy.types.Material.shred_custom_bake_quality = bpy.props.EnumProperty(items=[
        ("256", "Scratch (256)", "Scratch"),
        ("512", "Low (512)", "Low"),
        ("1024", "Medium (1024)", "Medium"),
        ("2048", "High (2048)", "High"),
    ])
    bpy.types.Material.shred_custom_quality_enabled = bpy.props.BoolProperty(default=False)
    bpy.types.Light.shred_static_shadows = bpy.props.BoolProperty()
    bpy.types.Light.shred_simple_diffuse = bpy.props.BoolProperty()
    bpy.app.timers.register(shred_export_undoer, persistent=True)
    bpy.utils.register_class(ShaderNodeShredVideoTexture)
    nodeitems_utils.register_node_categories("shredder", shred_node_categories)
    # bpy.app.handlers.save_pre.append(shred_save_handler)


def unregister():
    ShredAssets.del_object_props()
    del bpy.types.Scene.shred_bake_quality
    del bpy.types.Scene.shred_force_rebake
    del bpy.types.Light.shred_static_shadows
    del bpy.types.Light.shred_simple_diffuse
    del bpy.types.Material.shred_custom_bake_quality
    del bpy.types.Material.shred_custom_quality_enabled
    nodeitems_utils.unregister_node_categories("shredder")
    bpy.utils.unregister_class(ShaderNodeShredVideoTexture)


class shredPrepareObjects(bpy.types.Operator):
    bl_idname = "shred.prepare"
    bl_label = "Export"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        print('preparing objects for shred!')
        bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')

        # Step 1:
        # if the immediate parent is a curve, bake the movement action into object transform.
        # for object in bpy.data.objects:
        # 	if object.parent and object.parent.type == 'CURVE' and object.parent.data.use_path:
        # 		frame_end = object.parent.data.path_duration
        # 		bpy.ops.object.select_all(action='DESELECT')
        # 		object.select_set(True)
        # 		bpy.context.view_layer.objects.active = object
        # 		bpy.ops.nla.bake(frame_start=1, frame_end=frame_end, only_selected=False,
        # 						visual_keying=True, clear_constraints=True, clear_parents=True,
        # 						use_current_action=True, bake_types={'OBJECT'})
        # 		bpy.ops.object.select_all(action='DESELECT')

        # Step 2:
        # realize geometry node instances if they exist.
        for object in bpy.data.objects.values():
            if 'GeometryNodes' in object.modifiers.keys():
                physicsData.realize_evaluated_nodes(object)

        # Step 3:
        # re-apply the baking operator, considering that objects we've just realized might be parented to curves.
        for object in bpy.data.objects:
            if object.parent and object.parent.type == 'CURVE' and object.parent.data.use_path:
                parent_parent = object.parent.parent
                frame_end = object.parent.data.path_duration
                bpy.ops.object.select_all(action='DESELECT')
                object.select_set(True)
                bpy.context.view_layer.objects.active = object
                bpy.ops.nla.bake(frame_start=0, frame_end=frame_end, only_selected=False,
                                visual_keying=True, clear_constraints=True, clear_parents=True,
                                use_current_action=True, bake_types={'OBJECT'})
                bpy.ops.object.select_all(action='DESELECT')
                if parent_parent:
                    object.parent = parent_parent
                    object.matrix_parent_inverse = parent_parent.matrix_world.inverted()


        # Step 3:
        # Write shred properties to a dict called "shredder" for each object.
        physicsData.shredPreSave(None, None)

        # Step 4:
        # Export the GLTF file.
        filename = bpy.path.basename(bpy.context.blend_data.filepath)
        filebase = filename[:filename.rfind('.')]
        filepath = bpy.path.abspath(f"//" + filebase + "/")
        shred_export_gltf(filepath + filebase)

        global shred_gltf_export_completed
        shred_gltf_export_completed = True

        return{'FINISHED'}

component_enum = [
    ("script", "Script", "Shred Component"),
    ("camera", "Camera", "Shred Component"),
]

class shredAddComponentsOperator(bpy.types.Operator):
    bl_idname = "shred.op_add_components"
    bl_label = "COMPS"

    action: bpy.props.EnumProperty(items=ShredAssets.get_available_components)

    def execute(self, context):
        # reg_eval_str = f"context.active_object.shred_{self.action}"
        # exec(reg_eval_str)

        reg_eval_str = f"context.active_object.shredder.{self.action}"
        exec(reg_eval_str)

        print(self.action)
        return {'FINISHED'}

class shredAddComponentMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_add_shred_component"
    bl_label = "Add Component"

    def draw(self, context):
        lout = self.layout
        componentActionList = ShredAssets.get_available_components(self, context)
        for action in componentActionList:
            lout.operator("shred.op_add_components", text=action[1]).action = action[0]

class shredAddComponentButton(bpy.types.Operator):
    bl_idname = "shred.add_component_button"
    bl_label = "Add Component"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.wm.call_menu(name="OBJECT_MT_add_shred_component")
        return{'FINISHED'}


class shredRemoveComponent(bpy.types.Operator):
    bl_idname = "shred.remove_component"
    bl_label = "Remove"
    bl_options = {'REGISTER', 'UNDO'}
    bl_icon = "X"

    target_component: bpy.props.StringProperty()

    def execute(self, context):
        print(f'removing component {self.target_component}!')
        del context.active_object.shredder[self.target_component]
        return{'FINISHED'}

class shredSyncObjects(bpy.types.Operator):
    bl_idname = "shred.sync_engine"
    bl_label = "Update"
    bl_options = {'REGISTER'}

    def execute(self, context):
        print('syncing state with shred!')
        walk_shred_package()

        component_response = loadShredComponents()
        response = loadShredScripts()
        if "status" in response and response["status"] == "ok" and "response" in response:
            ShredAssets.component_propgroups = {}
            for key in component_response["response"]:
                ShredAssets.build_ecomponent_propgroup(key, component_response["response"][key])
                
            
            ShredAssets.scripts = response["response"]
            ShredAssets.buildScriptPropMap(ShredAssets.scripts)
            print(f"New script list: {ShredAssets.scripts}")
            ShredAssets.del_object_props()
            ShredAssets.register_object_props()

        return{'FINISHED'}


class shredLightningBake(bpy.types.Operator):
    bl_idname = "shred.lightning_bake"
    bl_label = "Lightning Bake"
    bl_options = {'REGISTER'}

    def execute(self, context):
        print('baking!')
        image_size = 512
        if "shred_bake_quality" in bpy.context.scene:
            image_size = int(bpy.context.scene.shred_bake_quality)
        ApplyLightningBake("lightning_test.png", image_size, image_size)
        return{'FINISHED'}


class shredORDERAComponentPanelPrototype(bpy.types.Panel):
    bl_idname = 'SHRED_PT_component_panel'
    bl_label = 'shredder'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "physics"
    #bl_parent_id = 'SHRED_PT_property_panel'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        current = context.active_object
        lout = self.layout
        lout.prop(current.shredder, "linked")

        if current.shredder.linked is None:
            lout.operator("shred.add_component_button")

            for key in ShredAssets.ecomponentPropMap:
                draw_component_props(current, context, lout, key, ShredAssets.ecomponentPropMap)

class shred_OT_scriptsearch(bpy.types.Operator):
    bl_idname = "shred.scriptsearch"
    bl_label = "Choose..."
    bl_property = "script_enum"

    script_enum: bpy.props.EnumProperty(items=ShredAssets.script_poll_callback)

    def execute(self, context):
        context.active_object.shredder.script.name = self.script_enum
        ShredAssets.script_update_func(None, context)
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}


class shred_OT_assetsearch(bpy.types.Operator):
    bl_idname = "shred.assetsearch"
    bl_label = "Choose..."
    bl_property = "asset_enum"
    bl_options = {'REGISTER'}

    asset_types = {'music': 'shred_music', 'midis': 'shred_midi',
        'sound_effect': 'shred_soundeffect', 'videos': 'shred_video', 'particles': 'shred_particle'}
    asset_type: bpy.props.StringProperty()


    def poll_callback(self, context):
        assets = []
        for asset in ShredAssets.file_assets[self.asset_type]:
            assets.append((asset, asset, "asset"))
        return ShredAssets.intern_enum_items_strings(assets)
    
    asset_enum: bpy.props.EnumProperty(items=poll_callback)

    @classmethod
    def description(cls, context, event):
        opt = getattr(event, "asset_type", "Something")
        return f"Choose {opt}"

    def execute(self, context):
        if self.asset_type == "music":
            context.active_object.shredder.music.file_name = ShredAssets.file_assets[self.asset_type][self.asset_enum]
        elif self.asset_type == "midis":
            context.active_object.shredder.music.accompanyingMidi = ShredAssets.file_assets[self.asset_type][self.asset_enum]
        elif self.asset_type == "videos":
            context.object.active_material.node_tree.nodes.active.video_file = ShredAssets.file_assets[self.asset_type][self.asset_enum]
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

class shred_PL_3DGlobalPanel(bpy.types.Panel):
    bl_idname = 'SHRED_PT_global_3d_panel'
    bl_label = 'shredder'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = "objectmode"
    bl_category = "shred"

    def draw(self, context):
        current = context.active_object

        lout = self.layout
        row = lout.row()
        row.operator("shred.sync_engine")
        row.operator("shred.prepare")
        baking = lout.box()
        baking.prop(context.scene, "shred_bake_quality", text="Bake Quality")
        baking.prop(context.scene, "shred_force_rebake", text="Force Bake")
        baking.operator("shred.lightning_bake")



class SHRED_LIGHT_PT_beam_shape(bpy.types.Panel):
    bl_idname = 'SHRED_PT_light_shading_model'
    bl_label = "Shred Shading Model"
    bl_parent_id = "CYCLES_LIGHT_PT_light"
    bl_context = "data"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        current = context.active_object

        lout = self.layout
        row = lout.row()
        baking = lout.box()
        baking.prop(context.active_object.data, "shred_static_shadows", text="Static Shadows")
        baking.prop(context.active_object.data, "shred_simple_diffuse", text="Simple Diffuse Only")

class SHRED_MATERIAL_PT_properties(bpy.types.Panel):
    bl_idname = 'SHRED_PT_material_properties'
    bl_label = "Shred Material Properties"
    #bl_parent_id = "CYCLES_LIGHT_PT_light"
    bl_context = "material"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'


    def draw(self, context):
        current = context.active_object

        lout = self.layout
        row = lout.row()
        baking = lout.box()
        baking.prop(context.active_object.active_material, "shred_custom_quality_enabled", text="Override Quality")
        if context.active_object.active_material.shred_custom_quality_enabled:
            baking.prop(context.active_object.active_material, "shred_custom_bake_quality", text="Bake Quality")

