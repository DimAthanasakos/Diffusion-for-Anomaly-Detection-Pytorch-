import json, yaml
import os
import time
import h5py as h5
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import gridspec
import matplotlib.ticker as mtick
from sklearn.utils import shuffle
import torch
import pandas as pd
import energyflow as ef
from torch.utils.data.distributed import DistributedSampler



#import energyflow as ef

np.random.seed(0) #fix the seed to keep track of validation split

line_style = {
    'true':'dotted',
    'gen':'-',    
}

colors = {
    'true':'silver',
    'gen':'firebrick',
}

name_translate={
    'true':'True backgound distribution',
    'gen':'Generated background distribution',
}


def reweight(data_j,data_p,model,mjj):
    mask = data_p[:,:,:,0]!=0
    weights = model.predict([data_j,data_p,mask,mjj], batch_size=1000,)
    weights = np.squeeze(np.ma.divide(weights,1.0-weights).filled(0))
    weights *= 1.0*weights.shape[0]/np.sum(weights)
    return weights

def get_mjj_mask(mjj,use_SR,mjjmin,mjjmax):
    if use_SR:
        mask_region = (mjj>=3300) & (mjj<=3700)
    else:
        mask_region = ((mjj<=3300) & (mjj>=mjjmin)) | ((mjj>=3700) & (mjj<=mjjmax))
    return mask_region

def SetStyle():
    from matplotlib import rc
    rc('text', usetex=True)

    import matplotlib as mpl
    rc('font', family='serif')
    rc('font', size=22)
    rc('xtick', labelsize=15)
    rc('ytick', labelsize=15)
    rc('legend', fontsize=15)

    # #
    mpl.rcParams.update({'font.size': 19})
    #mpl.rcParams.update({'legend.fontsize': 18})
    mpl.rcParams['text.usetex'] = False
    mpl.rcParams.update({'xtick.labelsize': 18}) 
    mpl.rcParams.update({'ytick.labelsize': 18}) 
    mpl.rcParams.update({'axes.labelsize': 18}) 
    mpl.rcParams.update({'legend.frameon': False}) 
    mpl.rcParams.update({'lines.linewidth': 2})
    
    import matplotlib.pyplot as plt
    import mplhep as hep
    hep.style.use(hep.style.CMS)
    
    # hep.style.use("CMS") 

def SetGrid(ratio=True):
    fig = plt.figure(figsize=(9, 9))
    if ratio:
        gs = gridspec.GridSpec(2, 1, height_ratios=[3,1]) 
        gs.update(wspace=0.025, hspace=0.1)
    else:
        gs = gridspec.GridSpec(1, 1)
    return fig,gs



        
def PlotRoutine(feed_dict,xlabel='',ylabel='',reference_name='gen'):
    assert reference_name in feed_dict.keys(), "ERROR: Don't know the reference distribution"
    
    fig,gs = SetGrid() 
    ax0 = plt.subplot(gs[0])
    plt.xticks(fontsize=0)
    ax1 = plt.subplot(gs[1],sharex=ax0)

    for ip,plot in enumerate(feed_dict.keys()):
        ax0.plot(np.mean(feed_dict[plot],0),label=plot,linestyle=line_style[plot],color=colors[plot])
        if reference_name!=plot:
            ratio = 100*np.divide(np.mean(feed_dict[reference_name],0)-np.mean(feed_dict[plot],0),np.mean(feed_dict[reference_name],0))
            #ax1.plot(ratio,color=colors[plot],marker='o',ms=10,lw=0,markerfacecolor='none',markeredgewidth=3)
            ax1.plot(ratio,color=colors[plot],linewidth=2,linestyle=line_style[plot])
                
        
    FormatFig(xlabel = "", ylabel = ylabel,ax0=ax0)
    ax0.legend(loc='best',fontsize=16,ncol=1)

    plt.ylabel('Difference. (%)')
    plt.xlabel(xlabel)
    plt.axhline(y=0.0, color='r', linestyle='--',linewidth=1)
    plt.axhline(y=10, color='r', linestyle='--',linewidth=1)
    plt.axhline(y=-10, color='r', linestyle='--',linewidth=1)
    plt.ylim([-30,30])

    return fig,ax0

class ScalarFormatterClass(mtick.ScalarFormatter):
    #https://www.tutorialspoint.com/show-decimal-places-and-scientific-notation-on-the-axis-of-a-matplotlib-plot
    def _set_format(self):
        self.format = "%1.1f"


def FormatFig(xlabel,ylabel,ax0):
    #Limit number of digits in ticks
    # y_loc, _ = plt.yticks()
    # y_update = ['%.1f' % y for y in y_loc]
    # plt.yticks(y_loc, y_update) 
    ax0.set_xlabel(xlabel,fontsize=20)
    ax0.set_ylabel(ylabel)
        

    # xposition = 0.9
    # yposition=1.03
    # text = 'H1'
    # WriteText(xposition,yposition,text,ax0)


def WriteText(xpos,ypos,text,ax0):

    plt.text(xpos, ypos,text,
             horizontalalignment='center',
             verticalalignment='center',
             transform = ax0.transAxes, fontsize=25, fontweight='bold')


def HistRoutine(feed_dict,
                xlabel='',ylabel='',
                reference_name='Geant',
                logy=False,binning=None,
                fig = None, gs = None,
                plot_ratio= True,
                idx = None,
                label_loc='best',
                rank = -1):
    assert reference_name in feed_dict.keys(), "ERROR: Don't know the reference distribution"
    #print(f'called HistRoutine with xlabel: {xlabel} and rank: {rank}')

    if fig is None:
        fig, gs = SetGrid(plot_ratio) 
    ax0 = plt.subplot(gs[0])
    if plot_ratio:
        plt.xticks(fontsize=0)
        ax1 = plt.subplot(gs[1],sharex=ax0)
        
    
    if binning is None:
        binning = np.linspace(np.quantile(feed_dict[reference_name],0.0),np.quantile(feed_dict[reference_name],1),30)
        
    xaxis = [(binning[i] + binning[i+1])/2.0 for i in range(len(binning)-1)]
    reference_hist,_ = np.histogram(feed_dict[reference_name],bins=binning,density=True)
    maxy = np.max(reference_hist)
    
    for ip,plot in enumerate(feed_dict.keys()):
        dist, _, _ = ax0.hist(feed_dict[plot],bins=binning, density=True, color = colors[plot], label=name_translate[plot], histtype="step" if plot == 'gen' else 'stepfilled')
        if plot_ratio:
            if reference_name!=plot:
                ratio = 100*np.divide(reference_hist-dist,reference_hist)
                ax1.plot(xaxis,ratio,color=colors[plot],marker='.',ms=15,lw=0,markerfacecolor='none',markeredgewidth=3)
        
    ax0.legend(loc=label_loc,fontsize=12,ncol=5)

    if logy:
        ax0.set_yscale('log')



    if plot_ratio:
        FormatFig(xlabel = "", ylabel = ylabel,ax0=ax0)
        plt.ylabel('Difference. (%)')
        plt.xlabel(xlabel)
        plt.axhline(y=0.0, color='r', linestyle='-',linewidth=1)
        # plt.axhline(y=10, color='r', linestyle='--',linewidth=1)
        # plt.axhline(y=-10, color='r', linestyle='--',linewidth=1)
        plt.ylim([-50,50])
    else:
        FormatFig(xlabel = xlabel, ylabel = ylabel,ax0=ax0)
    
    return fig, gs, binning


def LoadJson(file_name):
    import json,yaml
    JSONPATH = os.path.join(file_name)
    return yaml.safe_load(open(JSONPATH))

def SaveJson(save_file,data):
    with open(save_file,'w') as f:
        json.dump(data, f)


def SimpleLoader(data_path,file_name,use_SR=False,
                 npart=100,mjjmin=2300,mjjmax=5000):


    with h5.File(os.path.join(data_path,file_name),"r") as h5f:
        particles = h5f['constituents'][:]
        jets = h5f['jet_data'][:]
        mask = h5f['mask'][:]
        particles = np.concatenate([particles,mask],-1)

    p4_jets = ef.p4s_from_ptyphims(jets)
    # get mjj from p4_jets
    sum_p4 = p4_jets[:, 0] + p4_jets[:, 1]
    mjj = ef.ms_from_p4s(sum_p4)
    jets = np.concatenate([jets,np.sum(mask,-2)],-1)    

    # train using only the sidebands

    mask_region = get_mjj_mask(mjj,use_SR,mjjmin,mjjmax)
    mask_mass = (np.abs(jets[:,0,0])>0.0) & (np.abs(jets[:,1,0])>0.0)
    
    particles = particles[(mask_region) & (mask_mass)]
    mjj = mjj[(mask_region) & (mask_mass)]
    jets = jets[(mask_region) & (mask_mass)]
    jets[:,:,-1][jets[:,:,-1]<0] = 0.
    
    if not use_SR: # should nt this be the 10% not used for training in order to have a fair comparison?
        #Load validation split
        particles = particles[:int(0.9*jets.shape[0])]
        mask = mask[:int(0.9*jets.shape[0])]
        jets = jets[:int(0.9*jets.shape[0])]
    
    
    mask = np.expand_dims(particles[:,:,:,-1],-1)
    return particles[:,:,:,:-1]*mask,jets,mjj

        

def revert_npart(npart,max_npart,norm=None):
    #Revert the preprocessing to recover the particle multiplicity
    alpha = 1e-6
    data_dict = LoadJson('preprocessing_{}.json'.format(max_npart))
    if norm == 'mean':
        x = npart*data_dict['std_jet'][-1] + data_dict['mean_jet'][-1]
    elif norm == 'min':
        x = npart*(np.array(data_dict['max_jet'][-1]) - data_dict['min_jet'][-1]) + data_dict['min_jet'][-1]
    else:
        print("ERROR: give a normalization method!")
    return np.round(x).astype(np.int32)
     

def ReversePrep(particles,jets,mjj,npart,norm=None):
    alpha = 1e-6
    data_dict = LoadJson('preprocessing_{}.json'.format(npart))
    num_part = particles.shape[2]
    batch_size = particles.shape[0]
    particles=particles.reshape(-1,particles.shape[-1])
    jets=jets.reshape(-1,jets.shape[-1])
    mask = np.expand_dims(particles[:,0]!=0,-1)

    mjj_tile = np.expand_dims(mjj,1)
    mjj_tile = np.reshape(np.tile(mjj_tile,(1,2)),(-1))
    
    def _revert(x,name='jet'):
        if norm == 'mean':
            x = x*data_dict['std_{}'.format(name)] + data_dict['mean_{}'.format(name)]
        elif norm == 'min':
            x = x*(np.array(data_dict['max_{}'.format(name)]) - data_dict['min_{}'.format(name)]) + data_dict['min_{}'.format(name)]
        else:
            print("ERROR: give a normalization method!")

        return x
        
    particles = _revert(particles,'particle')
    jets = _revert(jets,'jet')
        
    jets[:,0] = np.exp(jets[:,0])*mjj_tile
    jets[:,4] = np.round(jets[:,4])
    jets[:,4] = np.clip(jets[:,4],1,npart)
    
    #1 particle jets have 0 mass
    mask_mass = jets[:,4]>1.0
    jets[:,3] = np.exp(jets[:,3])*mask_mass*mjj_tile
    
    particles[:,0] = 1.0 - np.exp(particles[:,0])
    particles[:,0] = np.clip(particles[:,0],2.5349376295699686e-05,1.0) #apply min pt cut 

        
    return (particles*mask).reshape(batch_size,2,num_part,-1),jets.reshape(batch_size,2,-1)


def LoadMjjFile(folder,file_name,use_SR,mjjmin=2300,mjjmax=5000):    
    with h5.File(os.path.join(folder,file_name),"r") as h5f:
        mjj = h5f['mjj'][:]


    mask = get_mjj_mask(mjj,use_SR,mjjmin,mjjmax)
    logmjj = prep_mjj(mjj)
    return logmjj[mask]

def revert_mjj(mjj,mjjmin=2300,mjjmax=5000):
    x = (mjj + 1.0)/2.0
    logmin = np.log(mjjmin)
    logmax = np.log(mjjmax)
    x = x * ( logmax - logmin ) + logmin
    return np.exp(x)

def prep_mjj(mjj,mjjmin=2300,mjjmax=5000):
    new_mjj = (np.log(mjj) - np.log(mjjmin))/(np.log(mjjmax) - np.log(mjjmin))
    new_mjj = 2*new_mjj -1.0
    return new_mjj




def DataLoader(data_path,file_name,
               npart,
               n_events,
               n_events_sample = 500,
               ddp = False,
               rank=0,size=1,
               batch_size=64,
               make_torch_data=True,
               use_SR=False,
               norm = None,
               mjjmin=2300,
               mjjmax=5000,):
    

#---------------------------------------------------------
    def _preprocessing(particles,jets,mjj,save_json=False):
        num_part = particles.shape[2]
        batch_size = particles.shape[0]

        jets[:,:,0] = jets[:,:,0]/np.expand_dims(mjj,-1)
        jets[:,:,3] = jets[:,:,3]/np.expand_dims(mjj,-1)
        
        particles=particles.reshape(-1,particles.shape[-1]) #flatten
        jets=jets.reshape(-1,jets.shape[-1]) #flatten

        
        #Transformations
        particles[:,0] = np.ma.log(1.0 - particles[:,0]).filled(0)
        jets[:,0] = np.log(jets[:,0])
        jets[:,3] = np.ma.log(jets[:,3]).filled(0)

        
        if save_json:
            mask = particles[:,-1]
            mean_particle = np.average(particles[:,:-1],axis=0,weights=mask)
            std_particle = np.sqrt(np.average((particles[:,:-1] - mean_particle)**2,axis=0,weights=mask))
            data_dict = {
                'max_jet':np.max(jets,0).tolist(),
                'min_jet':np.min(jets,0).tolist(),
                'max_particle':np.max(particles[:,:-1],0).tolist(),
                'min_particle':np.min(particles[:,:-1],0).tolist(),
                'mean_jet': np.mean(jets,0).tolist(),
                'std_jet': np.std(jets,0).tolist(),
                'mean_particle': mean_particle.tolist(),
                'std_particle': std_particle.tolist(),                     
            }                
            
            SaveJson('preprocessing_{}.json'.format(npart),data_dict)
        else:
            data_dict = LoadJson('preprocessing_{}.json'.format(npart))

            
        if norm == 'mean':
            jets = np.ma.divide(jets-data_dict['mean_jet'],data_dict['std_jet']).filled(0)
            particles[:,:-1]= np.ma.divide(particles[:,:-1]-data_dict['mean_particle'],data_dict['std_particle']).filled(0)
        elif norm == 'min':
            jets = np.ma.divide(jets-data_dict['min_jet'],np.array(data_dict['max_jet']) -data_dict['min_jet']).filled(0)
            particles[:,:-1]= np.ma.divide(particles[:,:-1]-data_dict['min_particle'],np.array(data_dict['max_particle']) - data_dict['min_particle']).filled(0)            
        else:
            print("ERROR: give a normalization method!")
        particles = particles.reshape(batch_size,2,num_part,-1)
        jets = jets.reshape(batch_size,2,-1)
        return particles.astype(np.float32),jets.astype(np.float32)

#---------------------------------------------------------
    
    with h5.File(os.path.join(data_path,file_name),"r") as h5f:
        nevts = min(n_events, h5f['jet_data'][:].shape[0])          # number of events
        particles = h5f['constituents'][:nevts]
        jets = h5f['jet_data'][:nevts]
        mask = h5f['mask'][:nevts]
        particles = np.concatenate([particles,mask],-1)

    # print the analytics of the data
    if rank == 0:
        print(f'nevts: {nevts}')
        print(f'Particles shape: {particles.shape}')
        print(f'Jets shape: {jets.shape}')
        print()


    p4_jets = ef.p4s_from_ptyphims(jets)
    # get mjj from p4_jets
    sum_p4 = p4_jets[:, 0] + p4_jets[:, 1]
    mjj = ef.ms_from_p4s(sum_p4)
    jets = np.concatenate([jets,np.sum(mask,-2)],-1)

    # train using only the sidebands
    mask_region = get_mjj_mask(mjj,use_SR,mjjmin,mjjmax)              # Only events in the sideband region (~80% of the events)
    mask_mass = (np.abs(jets[:,0,0])>0.0) & (np.abs(jets[:,1,0])>0.0) # Both jet have non-zero p_T (not zero padded events)
  
    #how many events outside mask_region and mask_mass
    if rank == 0:
        print(f'Number of events outside mask_region: {np.sum(~mask_region)}')
        print()
        print(f'Number of events inside mask_region: {np.sum(mask_region)}')
        print()

    particles = particles[(mask_region) & (mask_mass)]
    mjj = mjj[(mask_region) & (mask_mass)]
    jets = jets[(mask_region) & (mask_mass)]

    jets[:,:,-1][jets[:,:,-1]<0] = 0.
    #print(f'After masking with mask_region and mask_mass: {particles.shape}')
    #print(f'mjj.shape: {mjj.shape}')
    #print(f'jets.shape: {jets.shape}')

    if make_torch_data:
        # roughly 90%:10% split and rank-based slicing
        # original code: particles = particles[rank:int(0.65*nevts):size]
        # But note that we must recalculate based on (mask_region & mask_mass).
        # We'll assume the indexing logic as is:
        total_events = particles.shape[0]
        selected_indices = np.arange(total_events)[:int(0.90 * total_events)]
        particles = particles[selected_indices]
        jets = jets[selected_indices]
        mjj = mjj[selected_indices]    
    else:
        # This will be activated when we only want to load the data to compare the results with the generated data
        # for example, when we want to load the data in the SB region to use as condition to generate data and 
        # then compare them in the plot_jet.py
        if not use_SR:
            total_events = particles.shape[0]
            sliced_start = int(0.90 * total_events)
            sliced_indices = np.arange(sliced_start, total_events)[rank::size]
            particles = particles[sliced_indices]
            jets = jets[sliced_indices]
            mjj = mjj[sliced_indices]

    particles, jets, mjj = shuffle(particles,jets,mjj, random_state=0)
    data_size = jets.shape[0]

    if rank == 0:
        print(f'After masking with use_SR: {use_SR} : data_size: {data_size}')
        print()

    particles, jets = _preprocessing(particles, jets, mjj)

    # Normalize mjj to range [-1,1]
    mjj = prep_mjj(mjj, mjjmin, mjjmax)
    
    if make_torch_data:
        #roughly 90% train and 10% test
        split_index = int(0.9 * data_size)
        train_particles = particles[:split_index]
        train_jets = jets[:split_index]
        train_mjj = mjj[:split_index]

        test_particles = particles[split_index:]
        test_jets = jets[split_index:]
        test_mjj = mjj[split_index:]

        # mask for particles
        train_mask = np.expand_dims(train_particles[:, :, :, -1], -1)
        train_particles_masked = train_particles[:, :, :, :-1] * train_mask

        test_mask = np.expand_dims(test_particles[:, :, :, -1], -1)
        test_particles_masked = test_particles[:, :, :, :-1] * test_mask

        # Convert to tensors
        train_particles_t = torch.from_numpy(train_particles_masked)
        train_jets_t = torch.from_numpy(train_jets)
        train_mjj_t = torch.from_numpy(train_mjj)
        train_mask_t = torch.from_numpy(train_mask)

        test_particles_t = torch.from_numpy(test_particles_masked)
        test_jets_t = torch.from_numpy(test_jets)
        test_mjj_t = torch.from_numpy(test_mjj)
        test_mask_t = torch.from_numpy(test_mask)

        # Create TensorDatasets
        train_dataset = torch.utils.data.TensorDataset(train_particles_t, train_jets_t, train_mjj_t, train_mask_t)
        test_dataset = torch.utils.data.TensorDataset(test_particles_t, test_jets_t, test_mjj_t, test_mask_t)

        return data_size, train_dataset, test_dataset
  
    else:
        # Sampling case
        # Return first n_events_sample
        mask = np.expand_dims(particles[:n_events_sample, :, :, -1], -1)
        sampled_particles = particles[:n_events_sample, :, :, :-1] * mask
        sampled_jets = jets[:n_events_sample]
        sampled_mjj = mjj[:n_events_sample]
        
        return sampled_particles, sampled_jets, sampled_mjj, mask
