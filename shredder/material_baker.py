from enum import IntEnum, auto
import bpy
from .gpu_tools import draw_offscreen_3d
from dataclasses import dataclass, field, asdict

from .material_extensions import ShaderNodeShredVideoTexture

@dataclass
class TargetBackwardsLink:
    socket_name: str
    target_type: type
    target_socket: str


def check_links_match(start_node, chain):
    # walk backwards and compare nodes.
    current_node = start_node
    status = True
    for check_link in chain:
        if status and check_link.socket_name in current_node.inputs:
            current_link = current_node.inputs[check_link.socket_name].links[0]
            status = status and check_link.socket_name == current_link.to_socket.name
            status = status and isinstance(
                current_link.from_node, check_link.target_type)
            status = status and check_link.target_socket == current_link.from_socket.name
            if not status:
                return False
            current_node = current_link.from_node
        else:
            return False
    return status


def check_image_up_to_date(image_name, target_folder, image_size, non_color=False):
    image_exists = image_name in bpy.data.images
    if not image_exists:
        target_image = bpy.data.images.new(image_name, image_size, image_size)
        if non_color:
            target_image.colorspace_settings.name = "Non-Color"
        target_image.filepath = target_folder + image_name
    else:
        target_image = bpy.data.images[image_name]
        if target_image.generated_width != image_size or target_image.generated_height != image_size:
            image_exists = False
            print("Image size changed! Rebaking.")
            bpy.data.images.remove(target_image)
            target_image = bpy.data.images.new(
                image_name, image_size, image_size)

    return image_exists, target_image


def bake_to_texture(C, material, input_node, emission_node, image_name, target_folder, image_size):

    force_rebake = False
    if "shred_force_rebake" in bpy.context.scene:
        force_rebake = int(bpy.context.scene.shred_force_rebake)

    color_node = input_node.links[0].from_socket
    print(color_node)

    material.node_tree.links.new(color_node, emission_node.inputs["Color"])

    image_exists, target_image = check_image_up_to_date(
        image_name, target_folder, image_size)

    image_node = material.node_tree.nodes.new('ShaderNodeTexImage')
    image_node.select = True
    image_node.image = target_image
    material.node_tree.nodes.active = image_node

    if force_rebake or not image_exists:
        draw_offscreen_3d(C, image_name, image_size, image_size)
        # bpy.ops.object.bake(type="EMIT", save_mode="INTERNAL")
    else:
        print("Reusing albedo texture.")

    material.node_tree.links.new(
        input_node, image_node.outputs["Color"])

class MaterialInputAction(IntEnum):
    SKIP = 0
    BAKE = 1
    SHRED = 2


def process_material(material, force_rebake=False, target_folder="//exports/baked_textures/"):
    D = bpy.data
    C = bpy.context

    # bail out if nothing is using the material
    if material.users == 0:
        return

    # build match-chains to skip exportable-as-is node inputs.
    color_link_chain = [TargetBackwardsLink(
        "Base Color", bpy.types.ShaderNodeTexImage, "Color")]
    emission_link_chain = [TargetBackwardsLink(
        "Emission", bpy.types.ShaderNodeTexImage, "Color")]
    roughness_link_chain = [TargetBackwardsLink("Roughness", bpy.types.ShaderNodeSeparateColor, "Green"),
                            TargetBackwardsLink("Color", bpy.types.ShaderNodeTexImage, "Color")]
    metallic_link_chain = [TargetBackwardsLink("Metallic", bpy.types.ShaderNodeSeparateColor, "Blue"),
                           TargetBackwardsLink("Color", bpy.types.ShaderNodeTexImage, "Color")]
    normal_link_chain = [TargetBackwardsLink("Normal", bpy.types.ShaderNodeNormalMap, "Normal"),
                         TargetBackwardsLink("Color", bpy.types.ShaderNodeTexImage, "Color")]
    alpha_link_chain = [TargetBackwardsLink(
        "Alpha", bpy.types.ShaderNodeTexImage, "Alpha")]

    emission_video_chain = [TargetBackwardsLink("Emission", ShaderNodeShredVideoTexture, "Color")]

    checked_inputs = {"Base Color": MaterialInputAction.SKIP, "Emission": MaterialInputAction.SKIP,
                      "Metallic": MaterialInputAction.SKIP, "Roughness": MaterialInputAction.SKIP,
                        "Normal": MaterialInputAction.SKIP, "Alpha": MaterialInputAction.SKIP}
    # build skipping list
    skip_if = {
        "Base Color": color_link_chain,
        "Emission": emission_link_chain,
        "Alpha": alpha_link_chain,
        "Roughness": roughness_link_chain,
        "Metallic": metallic_link_chain,
        "Normal": normal_link_chain
    }

    # build node list for shred-specific node trees
    shred_if = {
        "Emission": emission_video_chain,
    }

    # walk material's node tree, compare nodes to match chains
    if material.node_tree is not None:
        output_node = material.node_tree.nodes["Material Output"]
        material_output_surface = output_node.inputs["Surface"]

        if (material_output_surface.is_linked):
            material_output_provider = material_output_surface.links[0].from_node

            # glass materials are converted to BRDF materials. "IOR" becomes "metallic".
            if isinstance(material_output_provider, bpy.types.ShaderNodeBsdfGlass):
                print("Glass material encountered.")
                if material.get("shredder", "") == "":
                    material["shredder"] = {}
                material["shredder"]["model"] = "glass"
                temp_brdf = material.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
                if material_output_provider.inputs["Color"].is_linked:
                    material.node_tree.links.new(
                        temp_brdf.inputs["Base Color"],
                        material_output_provider.inputs["Color"].links[0].from_socket)
                else:
                    temp_brdf.inputs["Base Color"].default_value = material_output_provider.inputs["Color"].default_value
                    
                if material_output_provider.inputs["Roughness"].is_linked:
                    material.node_tree.links.new(
                        temp_brdf.inputs["Roughness"],
                        material_output_provider.inputs["Roughness"].links[0].from_socket)
                else:
                    temp_brdf.inputs["Roughness"].default_value = material_output_provider.inputs["Roughness"].default_value
                
                if material_output_provider.inputs["IOR"].is_linked:
                    material.node_tree.links.new(
                        temp_brdf.inputs["Metallic"],
                        material_output_provider.inputs["IOR"].links[0].from_socket)
                else:
                    temp_brdf.inputs["Metallic"].default_value = material_output_provider.inputs["IOR"].default_value

                if material_output_provider.inputs["Normal"].is_linked:
                    material.node_tree.links.new(
                        temp_brdf.inputs["Normal"],
                        material_output_provider.inputs["Normal"].links[0].from_socket)
                
                material.node_tree.links.remove(output_node.inputs["Surface"].links[0])
                material.node_tree.links.new(temp_brdf.outputs["BSDF"], output_node.inputs["Surface"])
                material_output_provider = material_output_surface.links[0].from_node

            # BRDF materials are exported as-is after baking, as GLTF can handle them
            if isinstance(material_output_provider, bpy.types.ShaderNodeBsdfPrincipled):
                bsdf = material_output_provider
                for skippable in skip_if.keys():
                    if bsdf.inputs[skippable].is_linked:
                        skip = check_links_match(bsdf, skip_if[skippable])
                        if not skip:
                            checked_inputs[skippable] = MaterialInputAction.BAKE
                            # check whether the connection is to a shredder type
                            if (skippable in shred_if):
                                s_skip = check_links_match(bsdf, shred_if[skippable])
                                if s_skip:
                                    print("Found a node connected to an shred-specific channel!")
                                    checked_inputs[skippable] = MaterialInputAction.SHRED
                        print(f'has input: {skippable}, bake?: {checked_inputs[skippable]}')

    if any(checked_inputs.values()):
        # deduce target texture size
        image_size = 512
        if "shred_custom_quality_enabled" in material:
            if material.shred_custom_quality_enabled and "shred_custom_bake_quality" in material:
                image_size = int(material.shred_custom_bake_quality)
        else:
            if "shred_bake_quality" in bpy.context.scene:
                image_size = int(bpy.context.scene.shred_bake_quality)

        material_copy = material

        new_scene = bpy.ops.scene.new(type='NEW')
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.cycles.samples = 1

        bpy.ops.mesh.primitive_plane_add()
        new_plane = C.active_object
        print(new_plane)
        bpy.ops.object.material_slot_add()
        new_plane.data.materials[0] = material_copy

        output_node = material_copy.node_tree.nodes["Material Output"]
        emit_node = material_copy.node_tree.nodes.new('ShaderNodeEmission')

        brdf = output_node.inputs["Surface"].links[0].from_node
        print(brdf)
        remove_link = output_node.inputs["Surface"].links[0]
        material_copy.node_tree.links.remove(remove_link)
        material_copy.node_tree.links.new(
            emit_node.outputs["Emission"], output_node.inputs["Surface"])

        if checked_inputs["Base Color"] == MaterialInputAction.BAKE:
            albedo_image_name = material.name + "_albedo.simg.png"
            bake_to_texture(C, material_copy, brdf.inputs["Base Color"], emit_node, albedo_image_name, target_folder, image_size)

        if checked_inputs["Emission"] == MaterialInputAction.BAKE:
            image_name = material.name + "_emission.simg.png"
            bake_to_texture(C, material_copy, brdf.inputs["Emission"], emit_node, image_name, target_folder, image_size)
        elif checked_inputs["Emission"] == MaterialInputAction.SHRED:
            print("Emission node needs to be shredded...")
            shredder_node = brdf.inputs["Emission"].links[0].from_node
            shredder_node.shred(material_copy, "Emission")

        if checked_inputs["Alpha"] == MaterialInputAction.BAKE:
            image_name = material.name + "_alpha.simg.png"
            bake_to_texture(C, material_copy, brdf.inputs["Alpha"], emit_node, image_name, target_folder, image_size)
            

        if checked_inputs["Roughness"] == MaterialInputAction.BAKE or checked_inputs["Metallic"] == MaterialInputAction.BAKE:
            combine_node = material_copy.node_tree.nodes.new(
                'ShaderNodeCombineColor')
            # ambient occlusion not supported for now!
            combine_node.inputs["Red"].default_value = 1.0

            combine_link = material_copy.node_tree.links.new(
                combine_node.outputs["Color"], emit_node.inputs["Color"])

            if checked_inputs["Roughness"]:
                material_copy.node_tree.links.new(
                    brdf.inputs["Roughness"].links[0].from_socket, combine_node.inputs["Green"])
            else:
                # copy over constant roughness value.
                combine_node.inputs["Green"].default_value = brdf.inputs["Roughness"].default_value

            if checked_inputs["Metallic"]:
                material_copy.node_tree.links.new(
                    brdf.inputs["Metallic"].links[0].from_socket, combine_node.inputs["Blue"])
            else:
                # copy over constant roughness value.
                combine_node.inputs["Blue"].default_value = brdf.inputs["Metallic"].default_value

            arm_image_name = material.name + "_ARM.simg.png"
            image_exists, target_image = check_image_up_to_date(
                arm_image_name, target_folder, image_size, non_color=True)

            image_node = material_copy.node_tree.nodes.new(
                'ShaderNodeTexImage')
            image_node.select = True
            image_node.image = target_image
            material_copy.node_tree.nodes.active = image_node

            if force_rebake or not image_exists:
                draw_offscreen_3d(C, arm_image_name, image_size,
                                  image_size, color_image=False)
                # bpy.ops.object.bake(type="EMIT", save_mode="INTERNAL")
            else:
                print("Reusing ARM texture.")

            material_copy.node_tree.links.remove(combine_link)
            separate_node = material_copy.node_tree.nodes.new(
                'ShaderNodeSeparateColor')
            material_copy.node_tree.links.new(
                image_node.outputs["Color"], separate_node.inputs["Color"])
            material_copy.node_tree.links.new(
                separate_node.outputs["Green"], brdf.inputs["Roughness"])
            material_copy.node_tree.links.new(
                separate_node.outputs["Blue"], brdf.inputs["Metallic"])

        remove_link = output_node.inputs["Surface"].links[0]
        material_copy.node_tree.links.remove(remove_link)
        material_copy.node_tree.links.new(
            brdf.outputs["BSDF"], output_node.inputs["Surface"])

        if checked_inputs["Normal"] == MaterialInputAction.BAKE:
            normal_image_name = material.name + "_normal.simg.png"
            image_exists, target_image = check_image_up_to_date(
                normal_image_name, target_folder, image_size, non_color=True)

            image_node = material_copy.node_tree.nodes.new(
                'ShaderNodeTexImage')
            image_node.select = True
            image_node.image = target_image
            material_copy.node_tree.nodes.active = image_node

            if force_rebake or not image_exists:
                bpy.ops.object.bake(type="NORMAL", save_mode="INTERNAL")
            else:
                print("Reusing normal texture.")

            normal_map_node = material_copy.node_tree.nodes.new(
                'ShaderNodeNormalMap')
            material_copy.node_tree.links.new(
                normal_map_node.inputs["Color"], image_node.outputs["Color"])
            material_copy.node_tree.links.new(
                normal_map_node.outputs["Normal"], brdf.inputs["Normal"])

        bpy.ops.object.delete()
        print("done.")

        bpy.ops.scene.delete()

        return material_copy
    return None
