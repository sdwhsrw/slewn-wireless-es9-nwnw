# hw/

One folder per KiCad project, for example:

```
hw/main/main.kicad_pro  main.kicad_sch  main.kicad_pcb
hw/main/3d/             3D models for this board (reference them as ${KIPRJMOD}/3d/...)
```

Keep everything a board needs (3D models, local libraries) inside its folder, so the folder still works
when copied out as a plain KiCad project. `make check` runs ERC and DRC on every `hw/*/*.kicad_pro`.
