#! /Library/Frameworks/Python.framework/Versions/3.7/bin/python3
# ============================================== #
# ====== B: Coarse Grain Parameterization ====== #
# ============================================== #
# Written by Forrest Bicker
# August 2019
#


# ================ Dependencies ================ #
import numpy as np
import multiprocessing
import time

import MDAnalysis as mda
import BINAnalysis as boandi

from commands import cd
from commands import colorify


# ================ Input Files ================  #
topology = '/Users/forrestbicker/Desktop/test1-CG.psf'
trajectory = '/Users/forrestbicker/Desktop/test1-CG.dcd'

max_frame = 10000
stride = 1
block_count = 8


# ============= Pattern Generation ============= #
amino_acid_molds = {
    'LYS': {  # 3 segments
        'Bond': [['K21', 'K11'], ['K11', 'KB1'], ['KB1', 'KB2']],
        'Angle': [['K21', 'K11', 'KB1'], ['K11', 'KB1', 'KB2'], ['KB1', 'KB2', 'K12']],
        'Dihedral': [['K21', 'K11', 'KB1', 'KB2'], ['K11', 'KB1', 'KB2', 'K12'], ['KB1', 'KB2', 'K12', 'K22']]
    },
    'GLU DGLU': {  # 2 segments
        'Bond': [['E11', 'EB1'], ['EB1', 'EB2']],
        'Angle': [['E11', 'EB1', 'EB2'], ['EB1', 'EB2', 'E12']],
        'Dihedral': [['E11', 'EB1', 'EB2', 'E12']]
    },
    # 'ALA': {  # 1 segment
    #     'Bond': [['AB1', 'AB2']],
    #     'Angle': [['AB1', 'AB2', 'AB3']],
    #     'Dihedral': [['AB1', 'AB2', 'AB3', 'AB4']]
    # }
}


# ========= Multiprocessing Functions =========  #
# master multiprocessing function
def measure_all_connections(u, block_count, max_frame, stride):
    if block_count > 1:
        num_frames = len(u.trajectory[:max_frame])
        # determines size of each block
        block_size = int(np.ceil(num_frames / float(block_count)))

        # starting frame for each block
        starts = [n * block_size for n in range(block_count)]
        # ending frame for each block
        stops = [(n + 1) * block_size for n in range(block_count)]
        # stride length for each block (constant)
        strides = [stride for n in range(block_count)]
        block_id = [n for n in range(block_count)]  # numeric ID for each block

        # zips block information into one iterable
        arg_iter = zip(starts, stops, strides, block_id)

        with multiprocessing.Pool() as pool:  # pools blocks and runs in parallel
            # calls get_containers(params) for each block in arg_iter
            output_dict_list = pool.map(get_containers, arg_iter)

    elif block_count == 1:
        output_dict_list = get_containers([0, max_frame, stride, 0])

    else:
        raise ValueError(
            f'block_count must be greater than or equal to 1, but is {block_count}')

    return(output_dict_list)  # returns output from every block


# ============ Measurment Functions ============ #
def get_containers(arglist):
    # retrives block information from argument list
    start, stop, step, block_id = arglist

    fmt = 'Initiating Block {} for frames {} through {} with stride {}'
    print(fmt.format(block_id, start, stop, step))


    atms_dict = {}
    for resname_key, resname_dict in amino_acid_molds.items():  # three nested loops to acsess the beads
        for mes_type, component_list in resname_dict.items():
            sel = u.atoms.select_atoms(f'resname {resname_key}')
            sel_resids = sel.residues.resids
            for i, resid in enumerate(sel_resids):  # loops thru each resid
                for j, name_list in enumerate(component_list):
                    # generates selection paramets
                    params = gen_params(name_list, mes_type, sel_resids, resid)
                    mes_name = '_'.join(params[5:].split())
                    atms = u.atoms.select_atoms(params)
                    atms_dict[mes_name] = atms

    value_dict = {}
    for frame in u.trajectory:
        f = frame.frame
        if start <= f < stop:  # alterantive to slicing trajectory, because slicing breaks MDAnalysis in strange ways
            if f % step == 0:
                for mes_name, atms in atms_dict.items():
                    mes_type = mes_name.count('_') - 1
                    value = measure(mes_type, atms)
                    if value is not None:  # ensures that measurment exists
                        value_dict.setdefault(mes_name, []).append(value)  # safe append to dict
        elif f >= stop:
            print(colorify('32', f'Block {block_id} completed!'))
            return(value_dict)


def gen_params(name_list, mes_type, sel_resids, resid):
    mes_type_list = ['Bond', 'Angle', 'Dihedral']
    params = 'name'
    for name in name_list:
        i = int(name[2:])
        # ensures the function only works on mes_types that actually exist
        bool_list = [mes_type == item and resid + i < max(sel_resids) for item in enumerate(mes_type_list)]
        if bool_list:
            name = name[:2] + str(resid + i)
        else:
            pass  # ignores non-existent measurements
        params += (f' {name}')
    return(params)


def measure(mes_type, atms):
    if mes_type + 2 == len(atms):
        if mes_type == 0:  # bond
            return(atms.bond.length())
        elif mes_type == 1:  # angle
            return(atms.angle.angle())
        elif mes_type == 2:  # dihedral
            return(atms.dihedral.value())


# ============= Object Measurment =============  #
print('Generating Universe...')
u = mda.Universe(topology, trajectory)
print('Universe Generated!\nBegining Measurments:')


# logging information to screen
for resname_key, resname_dict in amino_acid_molds.items():
    try:
        for mes_type, connection_map in resname_dict.items():
            fmt = '- Measuring {} {} {}s in {} residues over {} frames'
            mes_count = len(connection_map)
            res_count = len(u.atoms.select_atoms(f'resname {resname_key}').residues)
            frame_count = len(u.trajectory[:max_frame]) + 1
            print(fmt.format(mes_count, resname_key, mes_type, res_count, frame_count))
    except IndexError:
        pass


master_container_dict = {}
s_time = time.time()
output_dict_list = measure_all_connections(u, block_count, max_frame, stride)
output_dict_list = filter(None, output_dict_list)
exec_time = time.time() - s_time


for output_dict in output_dict_list:  # combines each block's output
    for mes_name, values in output_dict.items():

        if mes_name not in master_container_dict.keys():  # ensures container exists in dict
            master_container_dict[mes_name] = boandi.Container(mes_name)

        container = master_container_dict[mes_name]
        container.add_values(values)  # combining outputs


# ========= Measruement Data Generation ========== #
cd('measurement_data')
print('\nExporting {} measurement datasets to file...'.format(
    len(master_container_dict)))
for container in master_container_dict.values():  # loops thru each measurement
    filename = f'{container.name}.dat'
    with open(filename, 'w') as instance_output:  # writes measurment list data to file
        # writes integer denoting mes_type to file
        instance_output.write(f'mes_type: {container.mes_type}\n')
        if container.mes_type == 0:
            str_values = [str(value) for value in container.values]
        else:
            str_values = [str(value * 3.14159 / 180) for value in container.values]
        instance_output.write('\n'.join(str_values))


# ============ File Object Cleanup ============  #
print('Outputs Written!\nTask Complete!')
print(f'Finished execution in {exec_time}s')