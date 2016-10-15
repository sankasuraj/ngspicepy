import string


from ctypes import c_bool, c_char_p, c_double, c_int, c_short,\
    c_void_p, cast, cdll, CFUNCTYPE, create_string_buffer,\
    POINTER, Structure
from os.path import isfile
from queue import Queue

import numpy as np

# Load the ngspice shared library.
# TODO: Figure out the path intelligently
libngspice = cdll.LoadLibrary("/usr/local/lib/libngspice.so.0")

send_char_queue = Queue()
send_stat_queue = Queue()
is_simulating = False


# enums for v_type
SV_NOTYPE         = 0
SV_TIME           = 1
SV_FREQUENCY      = 2
SV_VOLTAGE        = 3
SV_CURRENT        = 4
SV_OUTPUT_N_DENS  = 5
SV_OUTPUT_NOISE   = 6
SV_INPUT_N_DENS   = 7
SV_INPUT_NOISE    = 8
SV_POLE           = 9
SV_ZERO           = 10
SV_SPARAM         = 11
SV_TEMP           = 12
SV_RES            = 13
SV_IMPEDANCE      = 14
SV_ADMITTANCE     = 15
SV_POWER          = 16
SV_PHASE          = 17
SV_DB             = 18
SV_CAPACITANCE    = 19
SV_CHARGE         = 20


# C structs that are required by the shared library
class ngcomplex_t(Structure):
    _fields_ = [("cx_real", c_double),
                ("cx_imag", c_double)]


class vector_info(Structure):
    _fields_ = [("v_name", c_char_p),
                ("v_type", c_int),
                ("v_flags", c_short),
                ("v_realdata", POINTER(c_double)),
                ("v_compdata", POINTER(ngcomplex_t)),
                ("v_length", c_int)]


class vecinfo(Structure):
    _fields_ = [("number", c_int),
                ("vecname", c_char_p),
                ("is_real", c_bool),
                ("pdvec", c_void_p),
                ("pdvecscale", c_void_p)]


class vecinfoall(Structure):
    _fields_ = [("name", c_char_p),
                ("title", c_char_p),
                ("date", c_char_p),
                ("type", c_char_p),
                ("veccount", c_int),
                ("vecs", POINTER(POINTER(vecinfo)))]


class vecvalues(Structure):
    _fields_ = [("name", c_char_p),
                ("creal", c_double),
                ("cimag", c_double),
                ("is_scale", c_bool),
                ("is_complex", c_bool)]


class vecvaluesall(Structure):
    _fields_ = [("veccount", c_int),
                ("vecindex", c_int),
                ("vecsa", POINTER(POINTER(vecvalues)))]


# Callback functions
@CFUNCTYPE(c_int, c_int, c_bool, c_bool, c_int, c_void_p)
def ControlledExit(exit_status, is_unload, is_quit, lib_id, ret_ptr):
    if not exit_status == 0 or not is_quit:
        raise SystemError('Invalid command or netlist.')
    return 0


@CFUNCTYPE(c_int, c_char_p, c_int, c_void_p)
def SendChar(output, lib_id, ret_ptr):
    global send_char_queue

    clean_output = "".join(output.decode().split('*'))
    if 'stdout' in clean_output:
        to_print = ' '.join(clean_output.split(' ')[1:]).strip()
        if "ngspice" in to_print and "done" in to_print:
            send_char_queue.put("Quitting ngspice")
        elif "Note: 'quit' asks for detaching ngspice.dll" in to_print:
            pass
        elif to_print not in string.whitespace:
            send_char_queue.put(to_print)
    elif 'stderr' in clean_output:
        raise SystemError(" ".join(clean_output.split(' ')[1:]))
    return 0


@CFUNCTYPE(c_int, c_char_p, c_int, c_void_p)
def SendStat(sim_stat, lib_id, ret_ptr):
    send_stat_queue.put(sim_stat.decode())
    return 0


# Initialize ngspice
libngspice.ngSpice_Init(SendChar, SendStat, ControlledExit, None,
                        None, None)

# Specify API argument types and return types
libngspice.ngSpice_Command.argtypes = [c_char_p]
libngspice.ngGet_Vec_Info.argtypes  = [c_char_p]
libngspice.ngSpice_Circ.argtypes    = [POINTER(c_char_p)]
libngspice.ngSpice_AllVecs.argtypes = [c_char_p]

libngspice.ngSpice_Command.restype  = c_int
libngspice.ngSpice_running.restype  = c_int
libngspice.ngGet_Vec_Info.restype   = POINTER(vector_info)
libngspice.ngSpice_Circ.restype     = c_int
libngspice.ngSpice_CurPlot.restype  = c_char_p
libngspice.ngSpice_AllPlots.restype = POINTER(c_char_p)
libngspice.ngSpice_AllVecs.restype  = POINTER(c_char_p)


# User functions
def send_command(command):
    """Send a command to ngspice.

    The argument command is string that contains a valid ngspice
    command. See the chapter 'Interactive Interpreter' of the ngspice
    manual: http://ngspice.sourceforge.net/docs/ngspice26-manual.pdf
    """
    while not send_stat_queue.empty():
        send_stat_queue.get_nowait()

    libngspice.ngSpice_Command(create_string_buffer(command.encode()))

    output = []

    while not send_char_queue.empty():
        output.append(send_char_queue.get_nowait())
    return output


def run_dc(**kwargs):
    vstart = 0
    vstop = 10
    vincr = .1
    src2 = None
    start2 = None
    stop2 = None
    incr2 = None

    if vincr == 0:
        raise ValueError("Value of vincr cannt be zero")
    if vincr > 0 and vstart > vstop:
        raise ValueError("Inappropriate values of vincr, vstart or vstop")
    if vincr < 0 and vstart < vstop:
        raise ValueError("Inappropriate values of vincr, vstart or vstop")

    dc_args = [str(i) for i in kwargs]
    dc_command = ' '.join([i for i in dc_args])
    dc_result = send_command(dc_command)
    return dc_result


def run_ac(*kwargs):
   #nd, fstart, fstop = [(10,1,10) if 'dec' in kwargs]
   #no, fstart, fstop = [(10,1,2) if 'oct' in kwargs]
   #np, fstart, fstop = [(10,1,10) if 'lin' in kwargs]
   
   if fstart <= 0 or fstop <= 0:
    raise ValueError("Frequency cannot be negative or zero!!")
    
    ac_args = [ str(i) for i in kwargs]
    ac_command = ' '.join([ i for i in ac_args])
    ac_result = send_command(ac_command)
    return ac_result
    

def run_tran(*kwargs):
    tstep = "1n"
    tstop = "10n"
    tstart = 0
    tmax = None
    uic = None
    
    if tstep <= 0:
        raise ValueError(" Value of step cannot be zero")
    if tstart > tstop:
        raise ValueError("tstart cannot be greater that tstop")
    
    tran_args = [ str(i) for i in kwargs]
    tran_command = ' '.join([ i for i in tran_args])
    tran_result = send_command(tran_command)
    return tran_result
    
def run_op():
    op_result = send_command(op)
    return op_result


def get_plot_names():
    """Return a list of plot names.

    A plot is the name for a group of vectors. Example: A DC
    simulation run right after ngspice is loaded creates a plot called
    dc1 which contains the vectors generated by the DC simulation.
    """
    plot_name_array = libngspice.ngSpice_AllPlots()
    names_list = []
    name = plot_name_array[0]
    i = 1
    while name is not None:
        names_list.append(name.decode())
        name = plot_name_array[i]
        i += 1

    return names_list


# Function to return current plot
def current_plot():
    plot_name = libngspice.ngSpice_CurPlot()
    return (plot_name.decode())


def get_vector_names(plot_name=None):
    """Return a list of the names of the vectors in the given plot.

    plot_name specifies the plot whose vectors need to be returned. If
    it unspecified, the vector names from the current plot are
    returned.
    """

    if plot_name is None:
        plot_name = current_plot()

    if plot_name not in get_plot_names():
        raise ValueError("Given plot name doesn't exist")
    else:
        vector_names = libngspice.ngSpice_AllVecs(
            create_string_buffer(plot_name.encode()))
    names_list = []
    name = vector_names[0]
    i = 1
    while name is not None:
        names_list.append(name.decode())
        name = vector_names[i]
        i = i + 1

    return names_list


def get_data(vector_arg, plot_arg=None):

    if '.' in vector_arg:
        plot_name, vector_name = vector_arg.split('.')
        if vector_name not in get_vector_names(plot_name):
            raise ValueError("Inapproriate Vector Name")
    else:
        if vector_arg not in get_vector_names(plot_arg):
            raise ValueError("Inapproriate vector name")
        if plot_arg is not None:
            vector_arg = ".".join([plot_arg, vector_arg])

    info = libngspice.ngGet_Vec_Info(
        create_string_buffer(vector_arg.encode()))
    if info.contents.v_length <= 0:
        raise ValueError("Inapproriate vector name")
    else:
        data = np.squeeze(np.ctypeslib.as_array(
            info.contents.v_realdata, shape=(1, info.contents.v_length)))
    return data


def get_all_data(plot_name=None):
    """Return a dictionary of all vectors in the specified plot."""

    vector_names = get_vector_names(plot_name)

    vector_data = {}
    for vector_name in vector_names:
        print(vector_name)
        vector_data[vector_name] = get_data(vector_name)

    return vector_data


def set_options(*args, **kwargs):
    """Passes simulator options to ngspice.

    Options may either be entered as a string or keyword arguments.
    Examples:
    set_options(trtol=1, temp=300)
    set_options('trtol=1')
    """
    for option in args:
        send_command('option ' + str(option))
    for option in kwargs:
        if kwargs[option] is None:
            send_command('option ' + option)
        else:
            send_command('option ' + option + '=' +
                         str(kwargs[option]))


def load_netlist(netlist):
    """Load ngspice with the specified netlist.

    The argument netlist can be one of the following:
    1. The path to a file that contains the netlist.
    2. A list of strings where each string is one line of the netlist.
    3. A string containing the entire netlist with each line separated
    by a newline character.

    The function does not check if the netlist is valid. An invalid
    netlist may cause ngspice to crash.
    """
    if type(netlist) == str:
        if isfile(netlist):
            send_command('source ' + netlist)
            return
        else:
            netlist_list = netlist.split('\n')
    elif type(netlist) == list:
        netlist_list = netlist
    else:
        raise TypeError('Netlist format unsupported.\
                Must be a string or list')

    c_char_p_array = c_char_p * (len(netlist_list) + 1)
    netlist_str = c_char_p_array()

    for i, line in enumerate(netlist_list):
        netlist_str[i] = cast(create_string_buffer(line.encode()), c_char_p)
    netlist_str[len(netlist_list)] = None

    libngspice.ngSpice_Circ(netlist_str)
