import bpy

from nodeitems_utils import NodeCategory, NodeItem

class ShredderIDType(bpy.types.ID):
    # Define a string property called "my_string"
    my_string = bpy.props.StringProperty()
    
    # Define a method called "print_string"
    def print_string(self):
        print(self.my_string)

class ShaderNodeShredVideoTexture(bpy.types.ShaderNode):
    bl_idname = "shred.videoTextureNode"
    bl_description = "Video as a Texture"
    bl_label = "Video Texture"
    bl_icon = "IMAGE"

    video_file: bpy.props.StringProperty("")


    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'ShaderNodeTree'

    def init(self, context):
        print(context)
        color_multiplier_node = self.inputs.new('NodeSocketColor', "Color Multiplier")
        color_multiplier_node.default_value = [1, 1, 1, 1]
        self.inputs.new('NodeSocketVectorDirection', "UV")

        self.outputs.new('NodeSocketColor', "Color")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        searcher = layout.operator("shred.assetsearch", text="Video Picker")
        searcher.asset_type = "videos"
        layout.prop(self, "video_file")

    def shred(self, material, target_name):
        if material.get("shredder", "") == "":
            material["shredder"] = {}
        material["shredder"][target_name] = {"VideoTexture": self.video_file}

class ShredShaderNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        b = False
        # Make your node appear in different node trees by adding their bl_idname type here.
        if context.space_data.tree_type == 'ShaderNodeTree': b = True
        return b

# all categories in a list
shred_node_categories = [
    # identifier, label, items list
    ShredShaderNodeCategory("shredder", "shredder", items=[
        NodeItem("shred.videoTextureNode"),
        ]),
    ]


