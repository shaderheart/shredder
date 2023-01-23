
from cgitb import text
from collections.abc import Mapping
from hashlib import new
import json
import ctypes
from dataclasses import dataclass, field, asdict, fields
from enum import Enum, EnumMeta, IntEnum, auto
import random
import re
import shutil
import string
from xmlrpc.client import FastParser
import bpy
import platform

@dataclass
class shredScriptComponent:
	scriptName: str = ""
	varList: dict = field(default_factory=lambda: {})
	varString: str = ""

def test_update_function(self, context):
	print("UPDATE LOL!")

class shredCameraMode(IntEnum):
	EDIT = 0
	PLAY = auto()

class shredPhysicsShape(IntEnum):
	SPHERE = 0
	BOX = auto()
	CAPSULE = auto()
	BVH = auto()
	HEIGHTMAP = auto()
	COMPOUND = auto()
	MESH = auto()
	CONVEX = auto()
	INVALID = auto()

@dataclass
class shredMainPlayerComponent:
	empty = False

@dataclass
class shredTappableComponent:
	empty = False

class shredDynamicEnum:
	def __init__(self) -> None:
		self.enum_dict = {"undef": "undef"}
		self.enum_func = None
		self.update_func = None

@dataclass
class shredCameraComponent:
	active: bool = True
	fullView: bool = True
	zNear: float = 0.1
	zFar: float = 3000.0
	FOV: float = 90.0
	boomDistance: float = 10.0
	cameraMode: shredCameraMode = shredCameraMode.EDIT


@dataclass
class shredPhysicsComponent:
	shape: shredPhysicsShape = shredPhysicsShape.BOX
	kinematic: bool = False
	static: bool = False
	trigger: bool = False
	mass: float = 1.0
	friction: float = 0.5
	angular_damping: float = 0.5
	linear_damping: float = 0.5
	bounciness: float = 0.0
	margin: float = 0.04
	belongs: list = field(default_factory=lambda: [0])
	responds: list = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])


class shredEmptyEnum(Enum):
	undef = "undef"


def music_poll_callback(self, object):
	songs = []
	for song in ShredAssets.music:
		songs.append((song, song, "music"))
	return ShredAssets.intern_enum_items_strings(songs)

def script_poll_callback(self, object):
	scripts = []
	for script in ShredAssets.scripts:
		scripts.append((script, script, "script"))
	return ShredAssets.intern_enum_items_strings(scripts)


@dataclass
class shredScriptComponent:
	name: str = ""


@dataclass
class shredMusicComponent:
	file_name: str = ""
	accompanyingMidi: str = ""
	active: bool = False
	threeD: bool = False
	volume: float = 1.0
	outChannels: int = 2
	sourceChannel: int = 0
	multiMono: bool = False


@dataclass
class shredCharacterController:
	height: float = 2.0
	radius: float = 0.5


def buildComponentProperties(component_name, props):
	output = {}
	# inputs could be dicts or dataclasses.
	if isinstance(props, dict):
		prop_dict = props
	else:
		prop_dict = asdict(props)

	for key, value in prop_dict.items():
		prop_name = component_name + "var_" + key
		output[prop_name] = value
	return output

def injectComponentProperties(target, component_name, props):
	# inputs could be dicts or dataclasses.
	if isinstance(props, dict):
		prop_dict = props
	else:
		prop_dict = asdict(props)

	for key, value in prop_dict.items():
		prop_name = component_name + "var_" + key
		target[prop_name] = value

def clearComponentProperties(target, component_name):
	remove_vars = []
	for key in target.keys():
		if component_name + "var_" in key:
			remove_vars.append(key)
	for remove_var in remove_vars:
		del target[remove_var]

def getComponentProperties(target, component_name):
	output_vars = []
	for key in target.keys():
		if component_name + "var_" in key:
			output_vars.append(key)
	return output_vars


def loadShredScripts():
	path = bpy.path.abspath("//../scripts/scriptvars.json")
	scriptsVars = {}
	with open(path) as f:
		scriptsVars = json.load(f)
	shredScriptVars = {}

	for scriptVar in scriptsVars:
		shredScriptVars[scriptVar] = json.loads(scriptsVars[scriptVar])

	return {"status": "ok", "response": shredScriptVars}


def loadShredComponents():
	path = bpy.path.abspath("//../scripts/componentvars.json")
	componentVars = {}
	with open(path) as f:
		componentVars = json.load(f)
	shredComponentVars = {}

	for componentVar in componentVars:
		shredComponentVars[componentVar] = json.loads(componentVars[componentVar])

	return {"status": "ok", "response": shredComponentVars}



def draw_scriptvars(current, layout):
	scriptvars = getComponentProperties(current, "script")
	for svar in scriptvars:
		name = svar.replace("scriptvar_", "")
		name = re.sub('([A-Z]{1})', r' \1', name).lower()
		layout.prop(current, f'["{svar}"]', text=name)


def draw_component_props(current, context, layout, component_name, componentMap, recursed=False, parent_name=""):
	if (recursed) or ("shredder" in current and current.shredder.get(component_name, "") != ""):
		propdict = current.shredder.get(component_name, {})
		if propdict != {}:
			propdict =  propdict.to_dict()

		componentbox = layout.box()
		header = componentbox.row()
		if not recursed:
			exec(f'header.prop(current.shredder.{component_name}, "bpy_context_expanded", text="")')
			header.operator("shred.remove_component", icon="X", text="").target_component = component_name
		header.label(text=component_name + ':')
		if component_name == "script":
			header.operator("shred.scriptsearch", text="Script Picker")
		elif component_name == "music":
			header.operator("shred.assetsearch", text="Music Picker").asset_type = "music"
			header.operator("shred.assetsearch", text="MIDI Picker").asset_type = "midis"
		elif component_name == "midi":
			header.operator("shred.assetsearch", text="MIDI Picker").asset_type = "midis"

		if not recursed and ("bpy_context_expanded" not in propdict or not propdict["bpy_context_expanded"]):
			return

		if not isinstance(componentMap[component_name], dict):
			component_dict = (componentMap[component_name])
			for key in fields(component_dict):
				name = re.sub('([A-Z]{1})', r' \1', key.name).lower()
				exec(f'componentbox.row().prop(current.shredder.{component_name}, key.name, text=name)')
		else:
			component_dict = (componentMap[component_name])
			for key in (component_dict):
				currentVal = component_dict[key]
				if not isinstance(currentVal, dict):
					name = key # re.sub('([A-Z]{1})', r' \1', key).lower()
					if not recursed:
						exec(f'componentbox.row().prop(current.shredder.{component_name}, key, text=name)')
						# componentbox.row().prop(current.shredder[component_name], key, text=name)
					else:
						exec(f'componentbox.row().prop(current.shredder.{parent_name}.{component_name}, f"{key}", text=name)')
				else:
					draw_component_props(current, context, componentbox, key, component_dict, True, component_name)

		if component_name == "script":
			draw_scriptvars(current, componentbox)


class ShredAssets:
	scripts = {"undef": "undef"}
	music = {"yo": "yoo.ogg"}
	music_enum = Enum('Music', {el[0] : el[1] for el in music.items()}, type=str)
	sound_effects = {}
	midis = {}

	file_assets = {'music': {}, 'midis': {}, 'soundEffects': {}, 'impulses': {}, 'videos': {}, 'particles': {}}


	scriptPropMap = {}
	scriptVarMap = {}

	componentPropMap = {
		"script": shredScriptComponent(),
		"camera": shredCameraComponent(),
		"music": shredMusicComponent(),
		"physics": shredPhysicsComponent(),
		"character": shredCharacterController(),
		"mainplayer": shredMainPlayerComponent(),
		"tappable": shredTappableComponent(),
	}

	shredder_propgroup_data = {
		'bl_label': "shredder_propgroup",
		'bl_idname': "shredder.shredderpropgroup",
		'__annotations__': {"linked": bpy.props.PointerProperty(type=bpy.types.Object, name="Linked")}
	}

	ecomponentPropMap = {}

	component_propgroups = {}

	def buildScriptPropMap(scripts):
		for script in scripts:
			ShredAssets.scriptVarMap[script] = scripts[script]
			scriptdata = {
				'bl_label': "scr"+script,
				'bl_idname': "shredSCR."+script,
				"__annotations__": {}
			}
			for property in scripts[script]:
				scriptdata["__annotations__"][property] : ShredAssets.typedToProp(scripts[script][property], property)

			script_var_type = type("scr"+script, (bpy.types.PropertyGroup,), scriptdata)
			bpy.utils.register_class(script_var_type)
			ShredAssets.scriptPropMap[script] = script_var_type


	# To workaround the "known bug with using a callback" mentioned
	# in the EnumProperty docs, this function needs to be called on
	# any EnumProperty's items.
	ENUM_STRING_CACHE = {}
	def intern_enum_items_strings(items):
		def intern_string(s):
			if isinstance(s, str):
				ShredAssets.ENUM_STRING_CACHE.setdefault(s, s)
				s = ShredAssets.ENUM_STRING_CACHE[s]
			return s

		return [
			tuple([intern_string(s) for s in item])
			for item in items
		]

	
	def get_available_components(self, context):
		names = []
		for key, component in ShredAssets.ecomponentPropMap.items():
			names.append((key, key.capitalize(), "Shred Component"))

		return ShredAssets.intern_enum_items_strings(names)


	def script_poll_callback(self, object):
		scripts = []
		for script in ShredAssets.scripts:
			scripts.append((script, script, "script"))
		return ShredAssets.intern_enum_items_strings(scripts)

	def music_poll_callback(self, object):
		songs = []
		for song in ShredAssets.music:
			songs.append((song, song, "music"))
		return ShredAssets.intern_enum_items_strings(songs)

	def script_update_func(self, context):
		# go through properties, find script variables and remove them
		clearComponentProperties(context.active_object, "script")
		# now add variables of the current script
		scriptvars = ShredAssets.scriptVarMap[context.active_object.shredder.script.name]
		injectComponentProperties(context.active_object, "script", scriptvars)

	def build_component_propgroup(component_name):
		if not isinstance(ShredAssets.componentPropMap[component_name], dict):
			component = (ShredAssets.componentPropMap[component_name])
			component_dict = {}
			for key in fields(component):
				value = getattr(component, key.name)
				component_dict[key.name] = value
			ShredAssets.build_ecomponent_propgroup(component_name, component_dict)

	def build_ecomponent_propgroup(component_name, component_dict, recursed=False, parent_data={}):
			prop_list = []
			propgroup_data = {
				'bl_label': "propgroup" + component_name,
				'bl_idname': "shred.propgroup" + component_name,
				'__annotations__': {"bpy_context_expanded": bpy.props.BoolProperty(name = "", default = False)}
			}
			
			component_enum_list = []
			if not recursed:
				ShredAssets.ecomponentPropMap[component_name] = component_dict

			for key in (component_dict):
				value = (component_dict[key])

				if isinstance(value, dict):
					ShredAssets.build_ecomponent_propgroup(key, value, True, propgroup_data)
				elif isinstance(value, bool):
					propgroup_data["__annotations__"][key] = bpy.props.BoolProperty(name = key, default = value)
				elif isinstance(value, Enum):
					component_enum_list.append(key)
					if not hasattr(value, 'poll_func'):
						enumlist = []
						for name in type(value).__members__:
							enumlist.append((name, name, f"shred_{component_name}_{name}"))
						enumlist = ShredAssets.intern_enum_items_strings(enumlist)
					else:
						enumlist = value.poll_func

					update_func = value.update_func if hasattr(value, 'update_func') else None
					propgroup_data["__annotations__"][key] = bpy.props.EnumProperty(name=key, items=enumlist, update=update_func)

				elif isinstance(value, shredDynamicEnum):
					component_enum_list.append(key)
					propgroup_data["__annotations__"][key] = bpy.props.EnumProperty(name=key, items=value.enum_func, update=value.update_func)
				
				elif isinstance(value, float):
					propgroup_data["__annotations__"][key] = bpy.props.FloatProperty(name = key, default = value)
				elif isinstance(value, str):
					propgroup_data["__annotations__"][key] = bpy.props.StringProperty(name = key, default = value)
				elif isinstance(value, int):
					propgroup_data["__annotations__"][key] = bpy.props.IntProperty(name = key, default = value)
				elif isinstance(value, list):
					defaultFallback = True
					if len(value) > 0:
						if isinstance(value[0], float):
							if len(value) == 3:
								if key.lower().find("color") > -1:
									propgroup_data["__annotations__"][key] = bpy.props.FloatVectorProperty(size = len(value), default = value, subtype="COLOR", min=0, max=1)
								else:
									propgroup_data["__annotations__"][key] = bpy.props.FloatVectorProperty(size = len(value), default = value, subtype="XYZ", min=-100, max=100)
							else:
								propgroup_data["__annotations__"][key] = bpy.props.FloatVectorProperty(size = len(value), default = value)
							defaultFallback = False
					if defaultFallback:
						propgroup_data["__annotations__"][key] = bpy.props.BoolVectorProperty(size = 20, subtype="LAYER")

			propgroup = type("propgroup" + component_name, (bpy.types.PropertyGroup,), propgroup_data)
			bpy.utils.register_class(propgroup)
			proppointer = bpy.props.PointerProperty(type = propgroup)

			if recursed:
				parent_data["__annotations__"][component_name] = proppointer
			else:
				ShredAssets.component_propgroups[component_name] = propgroup
				ShredAssets.shredder_propgroup_data["__annotations__"][component_name] = proppointer
				shredder_propgroup = type("shredder_propgroup", (bpy.types.PropertyGroup,), ShredAssets.shredder_propgroup_data)
				bpy.utils.register_class(shredder_propgroup)
				shredder_proppointer = bpy.props.PointerProperty(type = shredder_propgroup)
				add_eval_str = f"bpy.types.Object.shredder = shredder_proppointer"
				res = exec(add_eval_str)
			pass

	def register_object_props():
		print("Registering shred components.")
		musicFinder = shredDynamicEnum()
		musicFinder.enum_func = ShredAssets.music_poll_callback
		scriptFinder = shredDynamicEnum()
		scriptFinder.enum_func = ShredAssets.script_poll_callback
		scriptFinder.update_func = ShredAssets.script_update_func

		for key in ShredAssets.componentPropMap:
			ShredAssets.build_component_propgroup(key)

	def del_object_props():
		try:
			for key in ShredAssets.componentPropMap:
				add_eval_str = f"del bpy.types.Object.shred_{key}"
				res = exec(add_eval_str)
		except:
			pass
