cd ~/desitarget/bin
./select_targets /project/projectdirs/desiproc/dr2/sweep/ /global/cscratch1/sd/forero/targetdata/decals_targets.fits
cd ~/mtl/bin
./build_mtl /global/cscratch1/sd/forero/targetdata/decals_targets.fits /global/cscratch1/sd/forero/specdata/spec1.fits /global/cscratch1/sd/forero/mtldata/mtl1.fits
cd ~/fiberassign/
./bin/assign /global/homes/f/forero/SandboxDESI/end2end/decals_dr2/inputs/fiberassign_pass_1.txt 