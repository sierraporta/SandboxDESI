import numpy as np
import desitarget.mtl
import os
import shutil
from desisim.quickcat import quickcat
import glob
import subprocess
from astropy.table import Table, Column

def mtl_assign_quickcat_loop(output_path=None, targets_path=None, zcat_file=None, fiberassign_exec=None, epoch_id=0):

    # create temporary output paths
    tmp_output_path = os.path.join(output_path, 'tmp/')
    if not os.path.exists(tmp_output_path):
        os.makedirs(tmp_output_path)

    tmp_fiber_path = os.path.join(tmp_output_path, 'fiberassign/')
    if not os.path.exists(tmp_fiber_path):
        os.makedirs(tmp_fiber_path)


    truth = Table.read(os.path.join(targets_path,'truth.fits'))
    targets = Table.read(os.path.join(targets_path,'targets.fits'))
    
    if zcat_file is None:
        mtl = desitarget.mtl.make_mtl(targets)
        mtl.write(os.path.join(tmp_output_path, 'mtl.fits'), overwrite=True)
    else:
        zcat = Table.read(zcat_file, format='fits')
        mtl = desitarget.mtl.make_mtl(targets, zcat)
        mtl.write(os.path.join(tmp_output_path, 'mtl.fits'), overwrite=True)
    print("Finished MTL")

    # clean fits files before fiberassing
    tilefiles = sorted(glob.glob(tmp_fiber_path+'/tile*.fits'))
    if tilefiles:
        for tilefile in tilefiles:
            os.remove(tilefile)
            
    # launch fiberassign
    p = subprocess.call([fiberassign_exec, os.path.join(tmp_output_path, 'fa_features.txt')], stdout=subprocess.PIPE)
    print("Finished fiberassign")

    #find the output fibermap tiles
    tilefiles = sorted(glob.glob(tmp_fiber_path+'/tile*.fits'))
    print("{} tiles in fiberassign output".format(len(tilefiles)))
    
    # write the zcat
    if zcat_file is None:
        zcat_file = os.path.join(tmp_output_path, 'zcat.fits')
        zcat = quickcat(tilefiles, targets, truth, zcat=None, perfect=False)
        zcat.write(zcat_file, overwrite=True)
    else:
        zcat_file = os.path.join(tmp_output_path, 'zcat.fits')
        zcat = Table.read(zcat_file, format='fits')
        newzcat = quickcat(tilefiles, targets, truth, zcat=zcat, perfect=False)
        newzcat.write(zcat_file, format='fits', overwrite=True)
    print("Finished zcat")

    # keep a copy of zcat.fits 
    epoch_output_path = os.path.join(output_path, '{}'.format(epoch_id))
    if not os.path.exists(epoch_output_path):
        os.makedirs(epoch_output_path)
    shutil.copy(zcat_file, epoch_output_path)

    return zcat_file

output_path =  "/project/projectdirs/desi/users/forero/lowfat/"
epoch_path = "/project/projectdirs/desi/mocks/preliminary/mtl/lowfat/"
targets_path = "/project/projectdirs/desi/mocks/preliminary/mtl/lowfat/"
fiberassign_exec = "/global/homes/f/forero/fiberassign/bin/./fiberassign"


if not os.path.exists(output_path):
    os.makedirs(output_path)

tmp_output_path = os.path.join(output_path, 'tmp/')
if not os.path.exists(tmp_output_path):
    os.makedirs(tmp_output_path)

tmp_fiber_path = os.path.join(tmp_output_path, 'fiberassign/')
if not os.path.exists(tmp_fiber_path):
    os.makedirs(tmp_fiber_path)

# create temporaty input file for fiberassign
params = ''.join(open('template_fiberassign.txt').readlines())
fx = open(os.path.join(tmp_output_path, 'fa_features.txt'), 'w')
fx.write(params.format(inputdir=tmp_output_path, targetdir=targets_path))
fx.close()

# loop over the epochs
n_epochs = 5
zcat_file = None
for i in range(n_epochs):
    epochfile = os.path.join(epoch_path, "epoch{}.txt".format(i))
    shutil.copy(epochfile, os.path.join(tmp_output_path, "survey_list.txt"))
                
    zcat_file = mtl_assign_quickcat_loop( 
        output_path = output_path, targets_path = targets_path,
        zcat_file = zcat_file, fiberassign_exec = fiberassign_exec, epoch_id = i)


#clean up tmp directory
if not os.path.exists(tmp_output_path):
    shutil.rmtree(tmp_output_path)
