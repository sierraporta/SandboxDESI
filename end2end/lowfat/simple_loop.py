import numpy as np
import desitarget.mtl
import os
import shutil
from desisim import quickcat
import glob
import subprocess
from astropy.table import Table, Column

def assign_quickcat_mtl_loop(destination_path=None, epoch_id = 0, targets_path=None, zcat_file=None, fiberassign_exec=None):

    truth = Table.read(os.path.join(targets_path,'truth.fits'))
    targets = Table.read(os.path.join(targets_path,'targets.fits'))
    
    if zcat_file is None:
        mtl = desitarget.mtl.make_mtl(targets)
        mtl.write(os.path.join(destination_path, 'mtl.fits'), overwrite=True)
    else:
        zcat = Table.read(zcat_file, format='fits')
        mtl = desitarget.mtl.make_mtl(targets, zcat)
        mtl.write(os.path.join(destination_path, 'mtl.fits'), overwrite=True)

#    p = subprocess.call([fiberassign_exec, fiberassign_features], stdout=subprocess.PIPE)
    p = subprocess.call([fiberassign_exec, os.path.join(destination_path, 'fa_features.txt')])

    #find the tiles
    fiberassign_output_path = os.path.join(destination_path, 'fiberassign/')
    if not os.path.exists(fiberassign_output_path):
            os.makedirs(fiberassign_output_path)
    tilefiles = sorted(glob.glob(fiberassign_output_path+'/tile*.fits'))
    print("{} tiles in fiberassign output".format(len(tilefiles)))

    #from desisim.quickcat import quickcat
    if zcat_file is None:
        zcat_file = os.path.join(destination_path, 'zcat.fits')
        zcat = quickcat.quickcat(tilefiles, targets, truth, zcat=None, perfect=False)
        zcat.write(zcat_file, overwrite=True)
    else:
        zcat_file = os.path.join(destination_path, 'zcat.fits')
        zcat = Table.read(zcat_file, format='fits')
        newzcat = quickcat.quickcat(tilefiles, targets, truth, zcat=zcat, perfect=False)
        newzcat.write(zcat_file, format='fits', overwrite=True)

    # keep a copy of zcat.fits 
    tmp_output_path = os.path.join(destination_path, '{}'.format(epoch_id))
    if not os.path.exists(tmp_output_path):
            os.makedirs(tmp_output_path)
    shutil.copy(zcat_file, tmp_output_path)

    #clean files
    for tilefile in tilefiles:
        os.remove(tilefile)
    return zcat_file

destination_path =  "/project/projectdirs/desi/users/forero/lowfat/"
epoch_path = "/project/projectdirs/desi/mocks/preliminary/mtl/lowfat/"
targets_path = "/project/projectdirs/desi/mocks/preliminary/mtl/lowfat/"
fiberassign_exec = "/global/homes/f/forero/fiberassign/bin/./fiberassign"
fiberassign_features = "/global/homes/f/forero/SandboxDESI/end2end/lowfat/fa_features.txt"

if not os.path.exists(destination_path):
    os.makedirs(destination_path)

params = ''.join(open('template_fiberassign.txt').readlines())
fx = open(os.path.join(destination_path, 'fa_features.txt'), 'w')
fx.write(params.format(inputdir=destination_path, targetdir=targets_path))
fx.close()


n_epochs = 5
zcat_file = None
for i in range(n_epochs):
    epochfile = os.path.join(epoch_path, "epoch{}.txt".format(i))
    shutil.copy(epochfile, os.path.join(destination_path, "survey_list.txt"))
                
    zcat_file = assign_quickcat_mtl_loop(
        destination_path = destination_path, epoch_id = i, targets_path = targets_path,
        zcat_file = zcat_file, fiberassign_exec = fiberassign_exec)

