# contains functions for plotting

import numpy as np

import matplotlib.pyplot as plt
plt.style.use('seaborn-whitegrid')
prop_cycle = plt.rcParams['axes.prop_cycle']
colors = prop_cycle.by_key()['color']
plt.rcParams.update({'font.size':12})

def show_IRFs(models,labels,varnames,
            abs_diff=None,lvl_value=None,facs=None,pows=None,
            do_shocks=True,do_targets=True,
            do_linear=False, do_non_linear=True,
            ncols=4,T_max=None, filename=None):

    assert do_linear or do_non_linear, 'plot at least one of the linear or non-linear IRFs'
    assert len(models) == 1 or not (do_linear and do_non_linear), 'comparison of linear and non-linear only available' \
                                                            ' with one model'
    # assert len(models) == 1 or not do_linear, 'comparision with linear only availible with one model'

    abs_diff = [] if abs_diff is None else abs_diff
    lvl_value = [] if lvl_value is None else lvl_value
    facs = {} if facs is None else facs
    pows = {} if pows is None else pows

    model = models[0]
    
    par = model.par
    if T_max is None: T_max = par.T
    
    # full_list
    full_list = []
    if do_shocks: full_list.append(('shocks',[x for x in model.shocks]))
    full_list.append(('varnames',varnames))
    if do_targets: full_list.append(('tagets',[x for x in model.targets]))
    
    # default fac = 1.0
    for (typename,varnames) in full_list:
        for varname in varnames:
            if not varname in facs: facs[varname] = 1.0
            if not varname in pows: pows[varname] = 1.0

    # figures
    for (typename,varnames) in full_list:
        
        print(f'### {typename} ###')
        
        num = len(varnames)
        nrows = num//ncols+1
        if num%ncols == 0: nrows -= 1 
            
        fig = plt.figure(figsize=(6*ncols,4*nrows),dpi=100)
        for i,varname in enumerate(varnames):
            
            ax = fig.add_subplot(nrows,ncols,i+1)
            title = varname
            if not np.isclose(pows[varname],1.0): title += (' (ann.)')
            ax.set_title(title,fontsize=14)
            
            for label,model_ in zip(labels,models):
            
                pathvalue = model_.path.__dict__[varname][0,:]
                IRFvalue = model_.IRF[varname]

                if not do_non_linear:
                    label_linear = label
                    ls_linear = '-'
                else:
                    label_linear = 'linear'
                    ls_linear = '--'

                if not np.isnan(getattr(model_.ss,varname)):

                    ssvalue = model_.ss.__dict__[varname]
                    IRFvalue = IRFvalue + ssvalue

                    if varname in abs_diff:
                        
                        if np.isclose(ssvalue,1.0):
                            ssvalue = facs[varname]*ssvalue**pows[varname]
                            pathvalue = facs[varname]*pathvalue**pows[varname]
                            IRFvalue = facs[varname]*IRFvalue**pows[varname]  
                        else:
                            ssvalue = facs[varname]*((1+ssvalue)**pows[varname]-1)
                            pathvalue = facs[varname]*((1+pathvalue)**pows[varname]-1)
                            IRFvalue = facs[varname]*((1+IRFvalue)**pows[varname]-1)

                        if do_non_linear:
                            ax.plot(np.arange(T_max),pathvalue[:T_max]-ssvalue,label=label)
                        if do_linear:
                            ax.plot(np.arange(T_max),IRFvalue[:T_max]-ssvalue,ls=ls_linear,label=label_linear)

                        if varname in facs:
                            ax.set_ylabel(fr'{facs[varname]:.0f} x abs. diff. to of s.s.')
                        else:
                            ax.set_ylabel('abs. diff. to of s.s.')

                    elif varname in lvl_value:
                        
                        if np.isclose(ssvalue,1.0):
                            ssvalue = facs[varname]*ssvalue**pows[varname]
                            pathvalue = facs[varname]*pathvalue**pows[varname]
                            IRFvalue = facs[varname]*IRFvalue**pows[varname]  
                        else:
                            ssvalue = facs[varname]*((1+ssvalue)**pows[varname]-1)
                            pathvalue = facs[varname]*((1+pathvalue)**pows[varname]-1)
                            IRFvalue = facs[varname]*((1+IRFvalue)**pows[varname]-1)

                        if do_non_linear:
                            ax.plot(np.arange(T_max),pathvalue[:T_max],label=label)
                        if do_linear:
                            ax.plot(np.arange(T_max),IRFvalue[:T_max],ls=ls_linear,label=label_linear)

                        if not np.isclose(facs[varname],1.0):
                            ax.set_ylabel(fr'{facs[varname]:.0f} x level')
                        else:
                            ax.set_ylabel('')

                    else:

                        if do_non_linear:
                            ax.plot(np.arange(T_max),100*(pathvalue[:T_max]/ssvalue-1),label=label)
                        if do_linear:
                            ax.plot(np.arange(T_max),100*(IRFvalue[:T_max]/ssvalue-1),ls=ls_linear,label=label_linear)

                        ax.set_ylabel('% diff. to s.s.')

                else:
                    if do_non_linear:
                        ax.plot(np.arange(T_max),pathvalue[:T_max],label=label)
                    if do_linear:
                        ax.plot(np.arange(T_max),IRFvalue[:T_max],ls=ls_linear,label=label_linear)

            if (len(labels) > 1 or (do_linear and do_non_linear)) and i == 0: ax.legend(frameon=True)
            # if (len(labels) > 1 or do_linear) and i == 0: ax.legend(frameon=True)
            
        fig.tight_layout(pad=3.0)
        plt.show()
        print('')

        # save
        if not filename is None: fig.savefig(filename)


