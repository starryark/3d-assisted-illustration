# Assets: what to build, what to obtain, and how to import it

## Four different things called "assets"

| Type | Provides | Example |
|---|---|---|
| 3D model | geometry with real depth, silhouette and surfaces | a building, a train, an air conditioner, a railing |
| Material / texture set | how a surface looks and reflects light | concrete colour, roughness and normal maps |
| HDRI | environment light from a panoramic image | an overcast sky, a sunset, an industrial interior |
| Decal / image | local surface detail or a flat element | a poster, a warning sign, a rust streak, a distant skyline |

A concrete material is not a building, and an HDRI lights a city without supplying any
geometry. Knowing which one you need makes searching much faster.

## Build or obtain?

> Model the forms that define your composition; obtain reusable objects whose complexity
> would otherwise consume your time.

The landmark whose silhouette carries the image: build it (`ia.kits.landmark_tower` is an
example). A recognisable motorbike, excavator or detailed appliance: obtain it. Save your
adapted pieces (building shells, roof assemblies, material setups) and you build up a
vocabulary for later scenes. The example scene in this repo is 100 % procedural, so it
builds anywhere with no downloads.

## Where to look

| Source | Good for | Notes |
|---|---|---|
| [Poly Haven](https://polyhaven.com/) | HDRIs, materials, some models | Published as CC0 ([license](https://polyhaven.com/license)). `tools/fetch_cc0.py` downloads by asset id and verifies each file against the MD5 Poly Haven publishes. |
| [ambientCG](https://ambientcg.com/) | concrete, asphalt, plaster, brick, painted metal… | Published as CC0 ([license](https://docs.ambientcg.com/license/)). Check that you're downloading the asset type you want. |
| [Blendkit](https://www.blendkit.com/) (formerly BlenderKit) | props, furniture, architectural pieces, materials | Free and paid, integrated in Blender. Read its licensing FAQ about selling renders versus redistributing models. |
| [KitBash3D](https://kitbash3d.com/) | cohesive building sets, industrial structures, skylines | Many pieces designed to work together. Check the product's formats and terms. |
| [Fab / Quixel Megascans](https://quixel.com/license) | scanned surfaces, rubble, rocks, plants, decals | Check each product's formats: an Unreal-oriented package may not include easily importable geometry. |
| [BOOTH](https://booth.pm/) | Japanese street details: utility poles, signs, storefronts | Search in Japanese (`電柱`, `室外機`, `看板`, `街並み`) and read each creator's terms. |
| [CGTrader](https://www.cgtrader.com/), [Sketchfab](https://sketchfab.com/features/free-3d-models) | one specific object | Licences vary per listing. Being able to view a model doesn't mean you can download it. |

**Licences vary per listing.** Read the licence attached to each item you use, and keep the
product page or licence with the asset. In practice, write a `manifest.json` next to it, as
`fetch_cc0.py` does. For finished illustrations, the usual distinction is between **using an
asset in an image** (normally allowed) and **redistributing the model itself** (normally not).
Never commit third-party models to a public repository.

Useful search terms: `modular`, `kit`, `facade`, `rooftop HVAC`, `pipe kit`, `elevated railway`,
`water tower`; 模块化建筑, 楼顶设备, 空调外机, 电线杆, 废墟模型; 背景 3D, 路地, 廃墟 (add `Blender` or `FBX`).

## Import hygiene (`ia.assets`)

Establish one clean source asset before you make fifty copies of it:

```python
objs = AS.import_file("downloads/vent.fbx", "Vent")      # only the objects this import created
rep  = AS.inspect(objs, expected_size=1.2)                # print + dict
objs = AS.drop_junk(objs)                                 # parentless bounds cubes etc.
AS.rebind_textures(objs, "downloads/vent_textures")       # paths from the author's machine
AS.fix_data_colorspaces(objs)                             # roughness/normal/... -> Non-Color
root = AS.normalize(objs, 1.2, axis="z")                  # real size, on z=0, centred
M.unify([m for o in objs for m in o.data.materials], saturation=0.85)
```

`inspect()` reports:

- size, and its ratio to the size you expected;
- polygon count and materials;
- missing textures;
- data maps mislabelled as sRGB;
- non-uniform or negative scale;
- parentless tiny meshes.

Things it can't fix for you:

- **materials authored for another renderer:** rebuild them with `M.image_pbr()`;
- **normal maps that need to change a silhouette:** a broken edge against the sky needs
  geometry;
- **hidden helper geometry** (rig widgets, weapon-holster rings): remove it with
  `strip_material_faces()` before measuring contacts. Such props can hold a lying body far
  above the ground.

Repetition: linked duplicates (shared mesh), collection instances (shared assemblies), and
geometry-nodes instances (`kits.scatter`). Keep instances as instances until you need to edit
one.
