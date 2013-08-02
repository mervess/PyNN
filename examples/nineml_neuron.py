"""
Example of using a cell type defined in 9ML
"""

import sys
from copy import deepcopy
from nineml.abstraction_layer.dynamics import (ComponentClass,
                                               Regime, On, OutputEvent,
                                               StateVariable, RecvPort,
                                               ReducePort,
                                               SendPort, SendEventPort)
from pyNN.utility import init_logging, get_simulator, normalized_filename

sim, options = get_simulator(("--plot-figure", "plot a figure with the given filename"))

init_logging(None, debug=True)

sim.setup(timestep=0.1, min_delay=0.1, max_delay=2.0)


iaf = ComponentClass(
    name="iaf",
    regimes=[
        Regime(
            name="subthresholdregime",
            time_derivatives=["dV/dt = ( gl*( vrest - V ) + ISyn)/(cm)"],
            transitions=On("V > vthresh",
                           do=["tspike = t",
                               "V = vreset",
                               OutputEvent('spikeoutput')],
                           to="refractoryregime"),
        ),
        Regime(
            name="refractoryregime",
            time_derivatives=["dV/dt = 0"],
            transitions=[On("t >= tspike + taurefrac",
                            to="subthresholdregime")],
        )
    ],
    state_variables=[
        StateVariable('V'),
        StateVariable('tspike'),
    ],
    analog_ports=[SendPort("V"),
                  ReducePort("ISyn", reduce_op="+"), ],

    event_ports=[SendEventPort('spikeoutput'), ],
    parameters=['cm', 'taurefrac', 'gl', 'vreset', 'vrest', 'vthresh']
)

coba = ComponentClass(
    name="CobaSyn",
    aliases=["I:=g*(vrev-V)", ],
    regimes=[
        Regime(
            name="cobadefaultregime",
            time_derivatives=["dg/dt = -g/tau", ],
            transitions=On('spikeinput', do=["g=g+q"]),
        )
    ],
    state_variables=[StateVariable('g')],
    analog_ports=[RecvPort("V"), SendPort("I"), ],
    parameters=['tau', 'q', 'vrev']
)

iaf_2coba = ComponentClass(
    name="iaf_2coba",
    subnodes={"iaf": iaf,
              "excitatory": coba,
              "inhibitory": deepcopy(coba)})
iaf_2coba.connect_ports("iaf.V", "excitatory.V")
iaf_2coba.connect_ports("iaf.V", "inhibitory.V")
iaf_2coba.connect_ports("excitatory.I", "iaf.ISyn")
iaf_2coba.connect_ports("inhibitory.I", "iaf.ISyn")

celltype_cls = sim.nineml.nineml_celltype_from_model(
                    name="iaf_2coba",
                    nineml_model=iaf_2coba,
                    synapse_components = [
                        sim.nineml.CoBaSyn(namespace='excitatory',  weight_connector='q'),
                        sim.nineml.CoBaSyn(namespace='inhibitory',  weight_connector='q')]
                    )

parameters = {
    'iaf_cm': 1.0,
    'iaf_gl': 50.0,
    'iaf_taurefrac': 2.0,
    'iaf_vrest': -65.0,
    'iaf_vreset': -65.0,
    'iaf_vthresh': -55.0,
    'excitatory_tau': 2.0,
    'inhibitory_tau': 5.0,
    'excitatory_vrev': 0.0,
    'inhibitory_vrev': -70.0,
}

print celltype_cls.default_parameters

cells = sim.Population(1, celltype_cls, parameters)
cells.initialize(iaf_V=parameters['iaf_vrest'])
cells.initialize(iaf_t_spike=-1e99)  # neuron not refractory at start

input = sim.Population(2, sim.SpikeSourcePoisson, {'rate': 500})

connector = sim.OneToOneConnector()
syn = sim.StaticSynapse(weight=5.0, delay=0.5)
conn = [sim.Projection(input[0:1], cells, connector, syn, receptor_type='excitatory'),
        sim.Projection(input[1:2], cells, connector, syn, receptor_type='inhibitory')]

cells.record(('spikes', 'iaf_V', 'excitatory_g', 'inhibitory_g'))

sim.run(100.0)

cells.write_data(
        normalized_filename("Results", "nineml_cell", "pkl",
                            options.simulator, sim.num_processes()),
        annotations={'script_name': __file__})

data = cells.get_data().segments[0]

sim.end()

if options.plot_figure:
    from pyNN.utility.plotting import Figure, Panel

    Figure(
        Panel(data.filter(name='iaf_V')[0]),
        Panel(data.filter(name='excitatory_g')[0], data.filter(name='inhibitory_g')[0],
              data_labels=['exc', 'inh'], ylabel="Synaptic conductance", xlabel="Time (ms)", xticks=True),
        title=__file__
    ).save(options.plot_figure)

    print data.spiketrains
