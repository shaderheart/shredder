import bpy
import gpu
from gpu_extras.presets import draw_texture_2d
from mathutils import Matrix
import math

def draw_offscreen_3d(context, image_name, width, height, color_image = True):
	show_origins_original = bpy.context.space_data.overlay.show_object_origins
	bpy.context.space_data.overlay.show_object_origins = False
	original_shading_type = bpy.context.space_data.shading.type
	bpy.context.space_data.shading.type = 'MATERIAL'
	original_render_pass = bpy.context.space_data.shading.render_pass
	bpy.context.space_data.shading.render_pass = 'EMISSION'
	original_show_axis_x = bpy.context.space_data.overlay.show_axis_x
	original_show_axis_y = bpy.context.space_data.overlay.show_axis_y
	original_show_floor = bpy.context.space_data.overlay.show_floor
	bpy.context.space_data.overlay.show_axis_x = False
	bpy.context.space_data.overlay.show_axis_y = False
	bpy.context.space_data.overlay.show_floor = False

	bpy.ops.view3d.localview()
	
	offscreen = gpu.types.GPUOffScreen(width, height)
	with offscreen.bind():
		scene = context.scene

		fb = gpu.state.active_framebuffer_get()
		fb.clear(color=(0.0, 0.0, 0.0, 0.0))

		# view_matrix = Matrix.Rotation(math.pi, 4, "X")
		view_matrix = Matrix.Identity(4)
		projection_matrix = Matrix.OrthoProjection('XY', 4)

		offscreen.draw_view3d(
				scene,
				context.view_layer,
				context.space_data,
				context.region,
				view_matrix,
				projection_matrix,
				do_color_management=color_image)

		buffer = fb.read_color(0, 0, width, height, 4, 0, 'UBYTE')
		
		if image_name not in bpy.data.images:
			bpy.data.images.new(image_name, width, height)
		image = bpy.data.images[image_name]
		image.scale(width, height)

		buffer.dimensions = width * height * 4
		image.pixels = [v / 255 for v in buffer]
	
	offscreen.free()

	bpy.context.space_data.overlay.show_object_origins = show_origins_original
	bpy.context.space_data.shading.type = original_shading_type
	bpy.context.space_data.shading.render_pass = original_render_pass
	bpy.context.space_data.overlay.show_axis_x = original_show_axis_x
	bpy.context.space_data.overlay.show_axis_y = original_show_axis_y
	bpy.context.space_data.overlay.show_floor = original_show_floor

	bpy.ops.view3d.localview()

	

def ApplyLightningBake(target_name, width, height):
	new_scene = bpy.ops.scene.new(type='NEW')
	print(new_scene)

	context = bpy.context

	for material in bpy.data.materials:
		bpy.ops.mesh.primitive_plane_add()
		new_plane = context.active_object
		print(new_plane)
		bpy.ops.object.material_slot_add()
		new_plane.data.materials[0] = material
		bpy.ops.view3d.localview()
		# new_plane.data.materials[0] = material
		print(material)
		
		image_name = material.name + target_name

		draw_offscreen_3d(context, image_name, width, height)
		
		bpy.context.view_layer.objects.active = new_plane
		new_plane.select_set(True)
		bpy.ops.view3d.localview()

		bpy.ops.object.delete()

	bpy.ops.scene.delete()


# bpy.types.SpaceView3D.draw_handler_add(draw, (), 'WINDOW', 'POST_PIXEL')
