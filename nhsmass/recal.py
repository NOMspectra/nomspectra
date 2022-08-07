#    Copyright 2022 Volikov Alexander <ab.volikov@gmail.com>
#
#    This file is part of nhsmass. 
#
#    nhsmass is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    nhsmass is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with nhsmass.  If not, see <http://www.gnu.org/licenses/>.

from typing import Optional, Tuple
import copy
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d
import scipy.stats as st

from .brutto import gen_from_brutto
from .spectrum import Spectrum

def recallibrate(spec: "Spectrum", 
                error_table: Optional["ErrorTable"] = None, 
                how: str = 'assign',
                draw: bool = True) -> "Spectrum":
    '''
    Recallibrate data by error-table

    Parameters
    ----------
    spec: Spectrum object
        Mass spectrum for recallibration
    error_table: ErrorTable object
        Optional. If None - calculate for spec. 
        ErrorTable object contain table error in ppm for mass, default 100 string            
    how: str
        Optional. Default 'assign'.
        If error_table is None we can choose how to recalculate.
        'assign' - by assign error, default.
        'mdm' - by calculation mass-difference map.
        filename - path to etalon spectrum, treated and saved by masslib
    draw: bool
        Plot error (fit of KDM)

    Returns
    -------
    Spectrum object with recallibrated mass
    '''
    spec = spec.copy()

    if error_table is None:
        if how == 'assign':
            error_table = ErrorTable().assign_error(spec, show_map=draw)
        elif how == 'mdm':
            error_table = ErrorTable().massdiff_error(spec, show_map=draw)
        else:
            etalon = Spectrum().read_csv(filename=how)
            error_table = ErrorTable().etalon_error(spec=spec, etalon=etalon, show_map=draw)

    err = copy.deepcopy(error_table.table)
    spec.table = spec.table.reset_index(drop=True)
    wide = len(err)

    min_mass = err['mass'].min()
    max_mass = err['mass'].max()
    a = np.linspace(min_mass, max_mass, wide+1)

    for i in range(wide):
        for ind in spec.table.loc[(spec.table['mass']>a[i]) & (spec.table['mass']<=a[i+1])].index:
            mass = spec.table.loc[ind, 'mass']
            e = mass * err.loc[i, 'ppm'] / 1000000
            spec.table.loc[ind, 'mass'] = spec.table.loc[ind, 'mass'] + e

    spec.metadata.add({'recallibrate':how})

    return spec


class ErrorTable(object):
    """
    A class used to recallibrate mass spectrum

    Attributes
    ----------
    table : pandas Datarame
        consist error table: error in ppm for mass
    """

    def __init__(
            self,
            table: Optional[pd.DataFrame] = None,
    ) -> None:
        """
        Init ErrorTable object

        Parameters
        ----------
        table : pandas Datarame
            consist error table: error in ppm for mass
        """
        self.table = table

    def md_error_map(
        self, 
        spec: "Spectrum", 
        ppm: float = 3, 
        show_map: Optional[bool] = False
        ) -> pd.DataFrame:
        '''
        Calculate mass differnce map

        Parameters
        ----------
        spec: pd.Dataframe
            Dataframe with spectrum table from Spectrum
        ppm: float
            Optional. Default 5.
            Permissible error in ppm
        show_map: bool
            Optional. Default False.
            Show error in ppm versus mass

        Return
        ------
        Pandas Dataframe object with calculated error map
        '''

        df = pd.DataFrame({ 'C':[1,1,1,2,0,1],
                            'H':[2,0,2,1,2,0],
                            'O':[0,1,1,1,1,2]})

        dif_masses = gen_from_brutto(df)['calc_mass'].values
        dif = np.unique([dif_masses*i for i in range(1,10)])

        data = copy.deepcopy(spec.table)
        masses = data['mass'].values

        data = data.sort_values(by='intensity', ascending=False).reset_index(drop=True)
        if len(data) > 1000:
            data = data[:1000]
        data = data.sort_values(by='mass').reset_index(drop=True)

        data_error = [] #array for new data

        for index, row in data.iterrows(): #take every mass in list
            
            mass = row["mass"]

            for i in dif:
                mz = mass + i #massdif

                idx = np.searchsorted(masses, mz, side='left')                
                if idx > 0 and (idx == len(masses) or np.fabs(mz - masses[idx - 1]) < np.fabs(mz - masses[idx])):
                    idx -= 1

                if np.fabs(masses[idx] - mz) / mz * 1e6 <= ppm:
                    data_error.append([mass, (masses[idx] - mz)/mz*1000000])
        
        df_error = pd.DataFrame(data = data_error, columns=['mass', 'ppm' ])
        
        if show_map:
            fig, ax = plt.subplots(figsize=(4, 4), dpi=75)
            ax.scatter(df_error['mass'], df_error['ppm'], s=0.01)

        return df_error
    
    def fit_kernel(
        self, 
        f: np.array,
        mass: np.array,
        err_ppm: float = 3,
        show_map: bool = True) -> pd.DataFrame:
        '''
        Fit max intesity of kernel density map

        Parameters
        ----------
        f: np.array
            keerndel density map in numpy array 100*100
        show_map: bool
            Optional. Default true.
            Plot how fit kernel

        Return
        ------
        Pandas Dataframe with error table for 100 values
        '''
        df = pd.DataFrame(f, index=np.linspace(3,-3,100))

        out = []
        for i in df.columns:
            max_kernel = df[i].quantile(q=0.95)
            ppm = df.loc[df[i] > max_kernel].index.values
            out.append([i, np.mean(ppm)])
        kde_err = pd.DataFrame(data=out, columns=['i','ppm'])
        
        #smooth data
        kde_err['ppm'] = savgol_filter(kde_err['ppm'], 31,5)
        
        xmin = min(mass)
        xmax = max(mass)
        
        #FIXME constan 100 maybe not good idea
        kde_err['mass'] = np.linspace(xmin, xmax, 100)

        ymin = -err_ppm
        ymax = err_ppm

        if show_map:
            fig = plt.figure(figsize=(4,4), dpi=75)
            ax = fig.gca()
            ax.set_xlim(xmin, xmax)
            ax.set_ylim(ymin, ymax)
            ax.imshow(df, extent=[xmin, xmax, ymin, ymax], aspect='auto')
            ax.plot(kde_err['mass'], kde_err['ppm'], c='r')
            ax.set_xlabel('m/z, Da')
            ax.set_ylabel('error, ppm')      

        #lock start at zero
        kde_err['ppm'] = kde_err['ppm'] - kde_err.loc[0,'ppm']

        return kde_err

    def kernel_density_map(
        self, 
        df_error: pd.DataFrame, 
        ppm: float = 3, 
        show_map: bool = False
        ) -> np.array:
        '''
        Plot kernel density map 100*100 for data

        Parameters
        ----------
        df_error: pd.Dataframe
            error_table for generate kerle density map
        ppm: float
            Optional. Default 3.
            treshould for generate
        show_map: bool
            Optional. Default True. plot kde

        Return
        ------
        numpy array 100*100 with generated kde
        '''
        
        x = np.array(df_error['mass'])
        y = np.array(df_error['ppm'])

        xmin = min(x) 
        xmax = max(x) 

        ymin = -ppm 
        ymax = ppm 

        #FIXME constan 100 maybe not good idea
        xx, yy = np.mgrid[xmin:xmax:100j, ymin:ymax:100j]

        positions = np.vstack([xx.ravel(), yy.ravel()])
        values = np.vstack([x, y])
        kernel = st.gaussian_kde(values)
        kdm = np.reshape(kernel(positions).T, xx.shape)
        kdm = np.rot90(kdm)

        if show_map:
            fig = plt.figure(figsize=(4,4), dpi=75)
            ax = fig.gca()
            ax.set_xlim(xmin, xmax)
            ax.set_ylim(ymin, ymax)
            ax.imshow(kdm, extent=[xmin, xmax, ymin, ymax], aspect='auto')
        
        return kdm

    def assign_error(
        self, 
        spec:Spectrum,
        ppm: float = 3,
        brutto_dict = {'C':(4,30), 'H':(4,60), 'O':(0,20)},
        show_map:bool = True):
        '''
        Recallibrate by assign error

        Parameters
        ----------
        spec: Spectrum object
            Initial mass spectrum for recallibrate
        ppm: float
            Permissible relative error in callibrate error. Default 3.
        brutto_dict: dict
            Dictonary with elements ranges for assignment
        show_error: bool
            Optional. Default True. Show process 

        Return
        ------
        ErrorTable object that contain recallabrate error ppm for mass diaposone

        '''
        spectr = copy.deepcopy(spec)
        spectr = spectr.assign(rel_error=ppm, brutto_dict=brutto_dict)
        spectr = spectr.calc_mass().calc_error()

        error_table = spectr.table
        error_table = error_table.loc[:,['mass','rel_error']]
        error_table.columns = ['mass', 'ppm']
        error_table['ppm'] = - error_table['ppm']
        error_table = error_table.dropna()

        kdm = self.kernel_density_map(df_error = error_table)
        err = self.fit_kernel(f=kdm, 
                            show_map=show_map, 
                            mass=spectr.drop_unassigned().table['mass'].values)
        self = ErrorTable(err).extrapolate((spec.table['mass'].min(), spec.table['mass'].max()))
        self = self.zeroshift(spectr)

        return self

    def massdiff_error(
        self,
        spec: Spectrum,
        show_map:bool = True):
        '''
        Self-recallibration of mass-spectra by mass-difference map

        Parameters
        -----------
        spec: Spectrum object
            Initial mass spectrum for recallibrate
        show_error: bool
            Optional. Default True. Show process 

        Return
        -------
        ErrorTable object that contain recallabrate error ppm for mass diaposone

        Reference
        ---------
        Smirnov, K. S., Forcisi, S., Moritz, F., Lucio, M., & Schmitt-Kopplin, P. 
        (2019). Mass difference maps and their application for the 
        recalibration of mass spectrometric data in nontargeted metabolomics. 
        Analytical chemistry, 91(5), 3350-3358. 
        '''
        spec = copy.deepcopy(spec)
        mde = self.md_error_map(spec = spec)
        kdm = self.kernel_density_map(df_error=mde)
        err = self.fit_kernel(f=kdm, show_map=show_map, mass=spec.table['mass'].values)
        
        return ErrorTable(err)

    def etalon_error( self,
                    spec: "Spectrum", #initial masspectr
                    etalon: "Spectrum", #etalon massspectr
                    quart: float = 0.9, #treshold by quartile
                    ppm: float = 3,#treshold by ppm
                    show_map: bool = True
                    ): 
        '''
        Recallibrate by etalon

        Parameters
        ----------
        spec: Spectrum object
            Initial mass spectrum for recallibrate
        etalon: Spectrum object
            Etalon mass spectrum
        quart: float
            Optionaly. by default it is 0.9. 
            Usualy it is enough for good callibration
            Quartile, which will be taken for calc recallibrate error
        ppm: float
            Optionaly. Default 3.
            permissible relative error in ppm for seak peak in etalon
        show_map: bool
            Optional. Default True. Show process 

        Return
        ------
        ErrorTable object that contain recallabrate error ppm for mass diaposone

        '''

        et = copy.deepcopy(etalon.table)['mass'].to_list()
        df = copy.deepcopy(spec.table)

        min_mass = df['mass'].min()
        max_mass = df['mass'].max()
        a = np.linspace(min_mass,max_mass,101)

        treshold = df['intensity'].quantile(quart)
        df = df.loc[df['intensity'] > treshold].reset_index(drop = True)
        df['cal'] = 0 #column for check

        #fill data massiv with correct mass
        for i in range(0,len(df)):
            min_mass = df.loc[i, 'mass']*(1 - ppm/1000000)
            max_mass = df.loc[i, 'mass']*(1 + ppm/1000000)
            for mass in et:
                try:
                    if mass > min_mass and mass < max_mass:
                        df.loc[i, 'cal'] = mass
                except:
                    pass
        
        # take just assigned peaks
        df = df.loc[df['cal']>0]
        #calc error and mean error
        df['dif'] = df['cal'] - df['mass']
        df['ppm']=df['dif']/df['mass']*1000000

        error_table = df.loc[:,['mass','ppm']]
        error_table = error_table.dropna()

        kdm = self.kernel_density_map(df_error = error_table)
        err = self.fit_kernel(f=kdm, show_map=show_map, mass=spec.table['mass'].values)

        return ErrorTable(err)

    def extrapolate(self, ranges:Tuple[float, float] = None) -> "ErrorTable":
        """
        Extrapolate error data

        Parameters
        ----------
        ranges: Tuple(numeric, numeric)
            Optionaly. Default None - all width of mass in error table.
            For which diaposone of mass extrapolate existin data

        Return
        ------
        ErrorTable object with extrapolated data
        """
        
        if ranges is None:
            ranges = [self.table['mass'].min(), self.table['mass'].max()]

        interpolation_range = np.linspace(ranges[0], ranges[1], 100)
        linear_interp = interp1d(self.table['mass'], self.table['ppm'],  bounds_error=False, fill_value='extrapolate')
        linear_results = linear_interp(interpolation_range)
        err = pd.DataFrame()
        err ['mass'] = interpolation_range
        err ['ppm'] = linear_results

        return ErrorTable(err)

    def show_error(self) -> None:
        """
        Plot error map from ErrorTable data
        """
        fig, ax = plt.subplots(figsize=(4,4), dpi=75)
        ax.plot(self.table['mass'], self.table['ppm'])
        ax.set_xlabel('m/z, Da')
        ax.set_ylabel('error, ppm')

    def zeroshift(self, spec:"Spectrum") -> "ErrorTable":
        """
        Shift error so mean eror will be zero

        Parameters
        ----------
        spec: Spectrum object
            income massspec

        Return
        ------
        ErrorTable object with shifted ppm error
        """
        err = copy.deepcopy(self)
        mean_error = spec.drop_unassigned().calc_error()['rel_error'].mean()
        err.table['ppm'] = err.table['ppm'] - mean_error
        return ErrorTable(err.table)


if __name__ == '__main__':
    pass