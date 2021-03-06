# we could move this to desiutil...
from __future__ import absolute_import, division, print_function

import os
import numpy as np

import fitsio
from scipy import constants 

from desitarget.io import check_fitsio_version, iter_files
from desitarget.mock.sample import SampleGMM
from desispec.brick import brickname as get_brickname_from_radec

import os
from time import time

import yaml
import numpy as np
from astropy.io import fits
from astropy.table import Table, Column, vstack

from desispec.io.util import fitsheader, write_bintable
from desispec.brick import brickname as get_brickname_from_radec

import desitarget.mock.io as mockio
import desitarget.mock.selection as mockselect
from desitarget.mock.spectra import MockSpectra
from desitarget.internal import sharedmem
from desitarget.targetmask import desi_mask, bgs_mask, mws_mask


from desispec.log import get_logger, DEBUG
from desispec.parallel import dist_uniform

import desitarget.mock.build as mockbuild

log = get_logger(DEBUG)

def countrows_gaussianfield(mock_dir_name, target_name):
    if target_name == 'SKY':
        mockfile = mock_dir_name
        columns = ['RA', 'DEC']
    else:
        from pathlib import Path
        f = Path(mock_dir_name)
        if f.is_file():
            mockfile = mock_dir_name
        else:
            mockfile = os.path.join(mock_dir_name, '{}.fits'.format(target_name.upper()))
    nrows = fitsio.FITS(mockfile)[1].get_nrows()
    return nrows

def cut_to_bounds(ra, dec, zz, bounds):
    nobj = len(ra)
    min_ra, max_ra, min_dec, max_dec = bounds
    cut = (ra >= min_ra) * (ra <= max_ra) * (dec >= min_dec) * (dec <= max_dec)
    if np.count_nonzero(cut) == 0:
        log.fatal('No objects in range RA={}, {}, Dec={}, {}!'.format(nobj, min_ra, max_ra, min_dec, max_dec))
        raise ValueError
    ra = ra[cut]
    dec = dec[cut]
    zz = zz[cut]
    nobj = len(ra)
    log.info('Trimmed to {} objects in range RA={}, {}, Dec={}, {}'.format(nobj, min_ra, max_ra, min_dec, max_dec))

def countrows_durham_mxxl_hdf5(mock_dir_name):
    import h5py

    mockfile = mock_dir_name
    try:
        os.stat(mockfile)
    except:
        log.fatal('Mock file {} not found!'.format(mockfile))
        raise IOError

    f = h5py.File(mockfile)
    ra  = f['Data/ra'][...].astype('f8') % 360.0
    nobj = len(ra)
    return nobj

def _sample_vdisp(logvdisp_meansig, nmodel=1, rand=None):
    """Choose a subset of velocity dispersions."""
    if rand is None:
        rand = np.random.RandomState()

    fracvdisp = (0.1, 40)

    nvdisp = int(np.max( ( np.min( ( np.round(nmodel * fracvdisp[0]), fracvdisp[1] ) ), 1 ) ))
    vvdisp = 10**rand.normal(logvdisp_meansig[0], logvdisp_meansig[1], nvdisp)
    vdisp = rand.choice(vvdisp, nmodel)

    return vdisp


def read_durham_mxxl_hdf5(mock_dir_name, target_name, 
                          bounds=None, magcut=None, rows=None):
    import h5py

    mockfile = mock_dir_name
    try:
        os.stat(mockfile)
    except:
        log.fatal('Mock file {} not found!'.format(mockfile))
        raise IOError

    f = h5py.File(mockfile)
    if rows is None:
        ra  = f['Data/ra'][...].astype('f8') % 360.0
        dec = f['Data/dec'][...].astype('f8')
        zz = f['Data/z_obs'][...].astype('f8')
        rmag = f['Data/app_mag'][...].astype('f8')
        absmag = f['Data/abs_mag'][...].astype('f8')
        gr = f['Data/g_r'][...].astype('f8')
    else:
        ra  = f['Data/ra'][rows].astype('f8') % 360.0
        dec = f['Data/dec'][rows].astype('f8')
        zz = f['Data/z_obs'][rows].astype('f8')
        rmag = f['Data/app_mag'][rows].astype('f8')
        absmag = f['Data/abs_mag'][rows].astype('f8')
        gr = f['Data/g_r'][rows].astype('f8')

    f.close()

    nobj = len(ra)
    vdisp = _sample_vdisp((1.9, 0.15), nmodel=nobj)
    log.info('Read {} objects from {}.'.format(nobj, mockfile))

    if bounds is not None:
        cut_to_bounds(ra, dec, zz, bounds)
    out = {'RA': ra, 'DEC': dec, 'Z': zz, 'MAG': rmag, 'VDISP':vdisp, 'SDSS_absmag_r01': absmag,
           'SDSS_01gr': gr, 'FILTERNAME': 'sdss2010-r','TEMPLATETYPE': 'BGS', 'TEMPLATESUBTYPE': '','TRUESPECTYPE': 'GALAXY'}
    return out



def read_gaussianfield(mock_dir_name, target_name,
               bounds=None, magcut=None, rows=None):
    if target_name == 'SKY':
        mockfile = mock_dir_name
        columns = ['RA', 'DEC']
    else:
        from pathlib import Path
        f = Path(mock_dir_name)
        if f.is_file():
            mockfile = mock_dir_name
        else:
            mockfile = os.path.join(mock_dir_name, '{}.fits'.format(target_name.upper()))

        columns = ['RA', 'DEC', 'Z_COSMO', 'DZ_RSD']        
    try:
        os.stat(mockfile)
    except:
        log.fatal('Mock file {} not found!'.format(mockfile))
        raise IOError

    if rows is None:
        data = fitsio.read(mockfile, columns=columns, upper=True)
    else:
        log.warning('Reading a subset')
        data = fitsio.read(mockfile, columns=columns, upper=True, rows=rows)
    
    ra = data['RA'].astype('f8') % 360.0 # enforce 0 < ra < 360
    dec = data['DEC'].astype('f8')
    if 'Z_COSMO' in data.dtype.names:
        zz = (data['Z_COSMO'].astype('f8') + data['DZ_RSD'].astype('f8')).astype('f4')
    else:
        zz = np.zeros_like(ra).astype('f4')

    if bounds is not None:
        cut_to_bounds(ra, dec, zz, bounds)

    out = {'RA': ra, 'DEC': dec, 'Z': zz}
    return out

def add_seed(input, rand):
    nobj = len(input['RA'])
    seed = rand.randint(2**32, size=nobj)
    input.update({'SEED':seed})

def add_GMM_gaussianfield(input, target_name, rand):
    if target_name == 'SKY':
        input.update({'TRUESPECTYPE': 'SKY', 'TEMPLATETYPE': 'SKY', 'TEMPLATESUBTYPE': ''})
    else:
        nobj = len(input['RA'])
        log.info('Sampling from Gaussian mixture model.')
        GMM = SampleGMM(random_state=rand)
        mags = GMM.sample(target_name, nobj) # [g, r, z, w1, w2, w3, w4]

        input.update({'GR': mags[:, 0]-mags[:, 1], 'RZ': mags[:, 1]-mags[:, 2],
                    'RW1': mags[:, 1]-mags[:, 3], 'W1W2': mags[:, 3]-mags[:, 4]})
    
        if target_name == 'ELG':
            """Selected in the r-band with g-r, r-z colors."""
            vdisp = 10**rand.normal(1.9, 0.15, nobj)
            input.update({'TRUESPECTYPE': 'GALAXY', 'TEMPLATETYPE': 'ELG', 'TEMPLATESUBTYPE': '',
                        'VDISP': vdisp, 'MAG': mags[:, 1], 'FILTERNAME': 'decam2014-r'})

        elif target_name == 'LRG':
            """Selected in the z-band with r-z, r-W1 colors."""
            vdisp = 10**rand.normal(2.3, 0.1, nobj)
            input.update({'TRUESPECTYPE': 'GALAXY', 'TEMPLATETYPE': 'LRG', 'TEMPLATESUBTYPE': '',
                        'VDISP': vdisp, 'MAG': mags[:, 2], 'FILTERNAME': 'decam2014-z'})
            
        elif target_name == 'QSO':
            """Selected in the r-band with g-r, r-z, and W1-W2 colors."""
            input.update({'TRUESPECTYPE': 'QSO', 'TEMPLATETYPE': 'QSO', 'TEMPLATESUBTYPE': '',
                        'MAG': mags[:, 1], 'FILTERNAME': 'decam2014-r'})
            
        else:
            log.fatal('Unrecognized target type {}!'.format(target_name))
            raise ValueError

def get_mock_spectra(mock_dir, target_name, mockformat, rand=None, comm=None):
    rank = comm.Get_rank()
    nproc = comm.Get_size()    
    nrows = None
    bounds = None
    Spectra = MockSpectra(rand=rand)
    SelectTargets = mockselect.SelectTargets(rand=rand)

    if rank ==0:
#        nrows = countrows_gaussianfield(mock_dir, target_name)
#        bounds = (0,1,-3,3)
        nrows = 100 * nproc


    nrows = comm.bcast(nrows, root=0)
    row_start, nrow = dist_uniform(nrows, nproc, rank)    
    print(rank, row_start, nrow)

    rows = range(row_start, row_start+nrow)

    read_function = 'read_{}'.format(mockformat)
    func = globals()[read_function]
    mock_data = func(mock_dir, target_name, rows=rows, bounds=bounds)

    if target_name not in ['BGS']:
        add_GMM_gaussianfield(mock_data, target_name, rand)

    add_seed(mock_data, rand=rand)

    nobj = len(mock_data['RA'])
    targets = mockbuild.empty_targets_table(nobj)
    truth = mockbuild.empty_truth_table(nobj)
    trueflux, meta = getattr(Spectra, target_name.lower())(mock_data, mockformat=mockformat)

    for key in ('TEMPLATEID', 'SEED', 'MAG', 'DECAM_FLUX', 'WISE_FLUX',
                'OIIFLUX', 'HBETAFLUX', 'TEFF', 'LOGG', 'FEH'):
        truth[key] = meta[key]

    # Perturb the photometry based on the variance on this brick.  Hack!  Assume
    # a constant depth (22.3-->1.2 nanomaggies, 23.8-->0.3 nanomaggies) in the
    # WISE bands for now.
    wise_onesigma = np.zeros((nobj, 2))
    wise_onesigma[:, 0] = 1.2
    wise_onesigma[:, 1] = 0.3
    targets['WISE_FLUX'] = truth['WISE_FLUX'] + rand.normal(scale=wise_onesigma)
    
    for band in (1, 2, 4):
        targets['DECAM_FLUX'][:, band] = truth['DECAM_FLUX'][:, band] 

    selection_function = '{}_select'.format(target_name.lower())
    getattr(SelectTargets, selection_function)(targets, truth)    
    targkeep = np.where(targets['DESI_TARGET'] != 0)[0]
    
    targets['RA'] = mock_data['RA']
    targets['DEC'] = mock_data['DEC']
    
    truth['TRUEZ'] = mock_data['Z'].astype('f4')
    truth['TEMPLATETYPE'] = mock_data['TEMPLATETYPE']
    truth['TEMPLATESUBTYPE'] = mock_data['TEMPLATESUBTYPE']
    truth['TRUESPECTYPE'] = mock_data['TRUESPECTYPE']

    return targets, truth, trueflux, targkeep

def do_it(comm):
    rand = np.random.RandomState()
    rank = comm.Get_rank()
    nproc = comm.Get_size()    
    mockpaths = ["/project/projectdirs/desi/mocks/GaussianRandomField/v0.0.4/",
                 "/project/projectdirs/desi/mocks/GaussianRandomField/v0.0.4/",
                 "/project/projectdirs/desi/mocks/bgs/MXXL/desi_footprint/v0.0.3/BGS_new_footprint.hdf5"]
    targetnames = ["ELG", "LRG", "BGS"]
    mockformats = ["gaussianfield", "gaussianfield", "durham_mxxl_hdf5"]

    #open fits files
    targetsfile = 'targets_proc_{}.fits'.format(rank)

    alltargets = list()
    alltruth = list()
    alltrueflux  = list()
    for mock_path, target_name, mock_format in zip(mockpaths, targetnames, mockformats):        
        targets, truth, trueflux, targkeep = get_mock_spectra(mock_path, target_name, mock_format, rand=rand, comm=comm)        
        print(rank, target_name, 'RA', len(targets['RA']), targets['RA'][0])

        alltargets.append(targets)
        alltruth.append(truth)
        alltrueflux.append(trueflux)
    
    targets = vstack(alltargets)
    truth = vstack(alltruth)
    trueflux = np.concatenate(alltrueflux)

    targets.write(targetsfile, overwrite=True)

    return 0

from mpi4py import MPI
comm = MPI.COMM_WORLD
do_it(comm)
