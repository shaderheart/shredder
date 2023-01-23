# shredder

Shredder is a Blender addon for my experimental game engine(s), so that I can use it as my level editor.

## Features
- Compatible with Blender 3.4+ on macOS, Linux and Windows
- Single-click scene file exports based on GLTF files
- Fast PBR material baking using offscreen 3D viewport rendering
- Baking curve-follow actions automatically
- Realizing non-mesh based geometry nodes on export, compatible with the GLTF exporter
- Component manager based on JSON script and component definitions for shred's ECS
- Parsing shred's file structure and presenting selectors for sound, video etc files

## Notes
- The GLTF exporter on Blender <3.5 has issues with handling bone-parented objects that lack an armature. You can get the newer version of the addon and replace the built-in one if you rely on this functionality.
- This is in early stages, and it's something that I'm developing in private for now. I want to get it out there as an additional motivation source. Everything is subject to change at any time. If any part of this interests you, you should clone the repository and isolate that part, so that it always works for you.
