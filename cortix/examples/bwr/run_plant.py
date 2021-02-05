#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This file is part of the Cortix toolkit environment
# https://cortix.org
"""Cortix Run File"""
import scipy.constants as unit
import matplotlib.pyplot as plt

from cortix import Cortix
from cortix import Network

from reactor import BWR
from turbine import Turbine
from condenser import Condenser
from cooler import Cooler
from params import get_params

def main():
    """Balance of plant of a boiling water nuclear reactor.

    Attributes
    ----------
    end_time: float
        End of the flow time in SI unit.
    time_step: float
        Size of the time step between port communications in SI unit.
    use_mpi: bool
        If set to `True` use MPI otherwise use Python multiprocessing.

    """

    # Preamble


    end_time = 300.0 * unit.minute
    time_step = 60.0 # seconds
    show_time = (True, 5*unit.minute)

    use_mpi = False  # True for MPI; False for Python multiprocessing
    plot_results = True # True for enabling plotting section below
    params = get_params() # parameters for BoP BWR

    #*****************************************************************************
    # Define Cortix system

    # System top level
    plant = Cortix(use_mpi=use_mpi, splash=True)

    # Network
    plant_net = plant.network = Network()

    params['start-time'] = 0.0
    params['end-time'] = end_time
    params['shutdown-time'] = 999.0 * unit.hour
    params['shutdown-mode'] = False
    #*****************************************************************************
    # Create reactor module
    reactor = BWR(params)

    reactor.name = 'BWR'
    reactor.save = True
    reactor.time_step = time_step
    reactor.end_time = end_time
    reactor.show_time = show_time
    reactor.RCIS = True
    reactor.RCIS_operating_mode = 'online'
    reactor.params['malfunction-start'] = 999.0 * unit.hour
    reactor.params['malfunction-end'] = 999.0 * unit.hour

    # Add reactor module to network
    plant_net.module(reactor)

    #*****************************************************************************
    # Create turbine high pressure module
    params['turbine_inlet_pressure'] = 7
    params['turbine_outlet_pressure'] = 0.5
    params['high_pressure_turbine'] = True

    #params_turbine = reactor.params
    #params_turbine.inlet_pressure = 2
    #params.turbine_outlet_pressure = 0.5

    turbine_hp = Turbine(params)

    turbine_hp.name = 'High Pressure Turbine'
    turbine_hp.save = True
    turbine_hp.time_step = time_step
    turbine_hp.end_time = end_time

    # Add turbine high pressure module to network
    plant_net.module(turbine_hp)

    #*****************************************************************************
    # Create turbine low pressure module
    params['turbine_inlet_pressure'] = 0.5
    params['turbine_outlet_pressure'] = 0.005
    params['high_pressure_turbine'] = False
    params['steam flowrate'] = params['steam flowrate']/2

    turbine_lp1 = Turbine(params)

    turbine_lp1.name = 'Low Pressure Turbine 1'
    turbine_lp1.save = True
    turbine_lp1.time_step = time_step
    turbine_lp1.end_time = end_time

    plant_net.module(turbine_lp1)

    #*****************************************************************************
    # Create turbine low pressure module
    params['turbine_inlet_pressure'] = 0.5
    params['turbine_outlet_pressure'] = 0.005
    params['high_pressure_turbine'] = False

    turbine_lp2 = Turbine(params)

    turbine_lp2.name = 'Low Pressure Turbine 2'
    turbine_lp2.save = True
    turbine_lp2.time_step = time_step
    turbine_lp2.end_time = end_time

    plant_net.module(turbine_lp2)

    #*****************************************************************************
    # Create condenser module
    params['steam flowrate'] = params['steam flowrate'] * 2
    params['malfunction-start'] = 999.0 * unit.hour
    params['malfunction-end'] = 999.0 * unit.hour
    condenser = Condenser()
    condenser.params = params

    condenser.name = 'Condenser'
    condenser.save = True
    condenser.time_step = time_step
    condenser.end_time = end_time

    plant_net.module(condenser)

    #*****************************************************************************
    params['RCIS-shutdown-time'] = 5 * unit.minute
    rcis = Cooler(params)
    rcis.name = 'RCIS'
    rcis.save = True
    rcis.time_step = time_step
    rcis.end_time = end_time

    plant_net.module(rcis)

    #*****************************************************************************
    # Create the BoP network connectivity
    plant_net.connect([reactor, 'coolant-outflow'], [turbine_hp, 'inflow'])
    plant_net.connect([turbine_hp, 'outflow-1'], [turbine_lp1, 'inflow'])
    plant_net.connect([turbine_hp, 'outflow-2'], [turbine_lp2, 'inflow'])
    plant_net.connect([turbine_lp1, 'outflow-1'], [condenser, 'inflow-1'])
    plant_net.connect([turbine_lp2, 'outflow-1'], [condenser, 'inflow-2'])
    plant_net.connect([condenser, 'outflow'], [reactor, 'coolant-inflow'])
    plant_net.connect([reactor, 'RCIS-outflow'], [rcis, 'coolant-inflow'])
    plant_net.connect([rcis, 'coolant-outflow'], [reactor, 'RCIS-inflow'])
    #plant_net.connect([rcis, 'signal-in'], [reactor, 'signal-out'])

    plant_net.draw(engine='dot', node_shape='folder')
    #*****************************************************************************
    # Run network dynamics simulation
    plant.run()

    #*****************************************************************************
    # Plot results

    if plot_results and (plant.use_multiprocessing or plant.rank == 0):

        # Reactor plots
        reactor = plant_net.modules[0]

        (quant, time_unit) = reactor.neutron_phase.get_quantity_history('neutron-dens')
        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']')

        plt.grid()
        plt.savefig('startup-neutron-dens.png', dpi=300)

        (quant, time_unit) = reactor.neutron_phase.get_quantity_history('delayed-neutrons-cc')
        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']')

        plt.grid()
        plt.savefig('startup-delayed-neutrons-cc.png', dpi=300)

        (quant, time_unit) = reactor.coolant_outflow_phase.get_quantity_history('temp')
        no_time_stamps = end_time/time_step

        coolant_temp = list()
        fuel_temp = list()
        neutron_dens = list()
        i=0

        while i < no_time_stamps:
            cool_temp = reactor.coolant_outflow_phase.get_value('temp', i * time_step)
            coolant_temp.append(cool_temp)
            fuel_tmp = reactor.reactor_phase.get_value('fuel-temp', i * time_step)
            fuel_temp.append(fuel_tmp)
            neut = reactor.neutron_phase.get_value('neutron-dens', i * time_step)
            neutron_dens.append(neut)
            i+=1

        q_f = list()
        q_c = list()
        z = 0
        while z < no_time_stamps:
            fuel_T = fuel_temp[z]
            cool_T = coolant_temp[z]
            n_dens = neutron_dens[z]
            fuel_q = reactor._BWR__nuclear_pwr_dens_func(0, (fuel_T + cool_T)/2, n_dens, reactor.params)
            fuel_q = fuel_q * reactor.fuel_volume
            cool_q = reactor._BWR__heat_sink_rate(0, fuel_T, cool_T, reactor.params)
            fuel_q *= -1
            cool_q *= -1
            q_f.append(fuel_q)
            q_c.append(cool_q)
            z = z+1

        x = 0
        time = list()
        while x < no_time_stamps:
            time.append((x * time_step)/60.0)
            fuelval = reactor.reactor_phase.get_value('fuel-temp', (x * time_step))
            fuel2 = (fuelval/9517) * 800 + reactor.reactor_phase.get_value('fuel-temp', 0.0)
            reactor.reactor_phase.set_value('fuel-temp', fuel2, (x * time_step))

            
            x += 1
        fuel3 = reactor.reactor_phase.get_value('fuel-temp', end_time)
        fuel3 = (fuel3/9517) * 800 + reactor.reactor_phase.get_value('fuel-temp', 0.0)
        reactor.reactor_phase.set_value('fuel-temp', fuel3, end_time)

        plt.plot(time, q_f, label='q_f')
        plt.plot(time, q_c, label='q_c')
        plt.title('heat')
        plt.xlabel('time')
        plt.xlabel('watts')
        plt.legend()
        plt.savefig('startup-heat.png', dpi=300)


        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']')

        plt.grid()
        plt.savefig('startup-coolant-outflow-temp.png', dpi=300)

        (quant, time_unit) = reactor.reactor_phase.get_quantity_history('fuel-temp')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']')
        plt.grid()
        plt.savefig('startup-fuel-temp.png', dpi=300)

        # Turbine high pressure plots
        turbine_hp = plant_net.modules[1]

        (quant, time_unit) = turbine_hp.outflow_phase.get_quantity_history('power')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']',
                   title='High Pressure Turbine Power')
        plt.grid()
        plt.savefig('startup-turbine-hp-power.png', dpi=300)

        (quant, time_unit) = turbine_hp.outflow_phase.get_quantity_history('temp')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']',
                   title='High Pressure Turbine Outflow Temperature')
        plt.grid()
        plt.savefig('startup-turbine-hp-outflow-temp.png', dpi=300)

        # Turbine low pressure graphs
        turbine_lp1 = plant_net.modules[2]

        (quant, time_unit) = turbine_lp1.outflow_phase.get_quantity_history('power')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']',
                   title='Lower Pressure Turbine 1 Power')
        plt.grid()
        plt.savefig('startup-turbine-lp1-power.png', dpi=300)

        (quant, time_unit) = turbine_lp1.outflow_phase.get_quantity_history('temp')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']',
                   title='Lower Pressure Turbine 1 Outflow Temperature')
        plt.grid()
        plt.savefig('startup-turbine-lp1-outflow-temp.png', dpi=300)

        # Condenser graphs
        condenser = plant_net.modules[3]

        (quant, time_unit) = condenser.outflow_phase.get_quantity_history('temp')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']')
        plt.grid()
        plt.savefig('startup-condenser-outflow-temp.png', dpi=300)


    #setup initial values for simulation
    turbine1_outflow_temp = turbine_hp.outflow_phase.get_value('temp', end_time)
    turbine1_chi = turbine_hp.outflow_phase.get_value('quality', end_time)
    turbine1_power = turbine_hp.outflow_phase.get_value('power', end_time)

    turbine2_outflow_temp = turbine_lp1.outflow_phase.get_value('temp', end_time)
    turbine2_chi = turbine_lp1.outflow_phase.get_value('quality', end_time)
    turbine2_power = turbine_lp1.outflow_phase.get_value('power', end_time)

    condenser_runoff_temp = condenser.outflow_phase.get_value('temp', end_time)

    delayed_neutron_cc = reactor.neutron_phase.get_value('delayed-neutrons-cc', end_time)
    n_dens = reactor.neutron_phase.get_value('neutron-dens', end_time)
    fuel_temp = reactor.reactor_phase.get_value('fuel-temp', end_time)
    coolant_temp = reactor.coolant_outflow_phase.get_value('temp', end_time)
    # Values loaded into params when they are needed (module instantiation)

    # Properly shutdown simulation
    plant.close()

    # Now we run shutdown as a seperate simulation with starting parameters equal to the ending
    # values of the startup simulation

#**************************************************************************************************

    # Preamble

    start_time = 0.0 * unit.minute
    end_time = 60 * unit.minute
    time_step = 30.0 # seconds
    show_time = (True, 5*unit.minute)

    use_mpi = False  # True for MPI; False for Python multiprocessing
    plot_results = True # True for enabling plotting section below
    params = get_params() # clear params, just to be safe

    #*****************************************************************************
    # Define Cortix system

    # System top level
    plant = Cortix(use_mpi=use_mpi, splash=True)

    # Network
    plant_net = plant.network = Network()

    params['start-time'] = start_time
    params['end-time'] = end_time
    params['shutdown time'] = 999.0 * unit.hour
    params['shutdown-mode'] = False

    #*****************************************************************************
    # Create reactor module
    params['delayed-neutron-cc'] = delayed_neutron_cc
    params['n-dens'] = n_dens
    params['fuel-temp'] = fuel_temp
    params['coolant-temp'] = coolant_temp
    params['operating-mode'] = 'startup'
    params['malfunction-start'] = 5 * unit.minute
    params['malfunction-end'] = 15 * unit.minute
    reactor = BWR(params)

    reactor.name = 'BWR'
    reactor.save = True
    reactor.time_step = time_step
    reactor.end_time = end_time
    reactor.show_time = show_time
    reactor.RCIS = False

    # Add reactor module to network
    plant_net.module(reactor)

    #*****************************************************************************
    # Create turbine high pressure module
    params['turbine_inlet_pressure'] = 2
    params['turbine_outlet_pressure'] = 0.5
    params['high_pressure_turbine'] = True
    params['turbine-outflow-temp'] = turbine1_outflow_temp
    params['turbine-chi'] = turbine1_chi
    params['turbine-work'] = turbine1_power
    params['turbine-inflow-temp'] = coolant_temp

    #params_turbine = reactor.params
    #params_turbine.inlet_pressure = 2
    #params.turbine_outlet_pressure = 0.5

    turbine_hp = Turbine(params)

    turbine_hp.name = 'High Pressure Turbine'
    turbine_hp.save = True
    turbine_hp.time_step = time_step
    turbine_hp.end_time = end_time

    # Add turbine high pressure module to network
    plant_net.module(turbine_hp)

    #*****************************************************************************
    # Create turbine low pressure 1 module
    params['turbine_inlet_pressure'] = 0.5
    params['turbine_outlet_pressure'] = 0.005
    params['high_pressure_turbine'] = False
    params['steam flowrate'] = params['steam flowrate']/2
    params['turbine-outflow-temp'] = turbine2_outflow_temp
    params['turbine-inflow-temp'] = turbine1_outflow_temp
    params['turbine-chi'] = turbine2_chi
    params['turbine-work'] = turbine2_power

    turbine_lp1 = Turbine(params)

    turbine_lp1.name = 'Low Pressure Turbine 1'
    turbine_lp1.save = True
    turbine_lp1.time_step = time_step
    turbine_lp1.end_time = end_time

    plant_net.module(turbine_lp1)

    #*****************************************************************************
    # Create turbine low pressure 2 module
    params['turbine_inlet_pressure'] = 0.5
    params['turbine_outlet_pressure'] = 0.005
    params['high_pressure_turbine'] = False

    turbine_lp2 = Turbine(params)

    turbine_lp2.name = 'Low Pressure Turbine 2'
    turbine_lp2.save = True
    turbine_lp2.time_step = time_step
    turbine_lp2.end_time = end_time

    plant_net.module(turbine_lp2)

    #*****************************************************************************
    # Create condenser module
    params['steam flowrate'] = params['steam flowrate'] * 2
    params['condenser-runoff-temp'] = condenser_runoff_temp
    params['malfunction-start'] = 5 * unit.minute
    params['malfunction-end'] = 15 * unit.minute
    condenser = Condenser()
    condenser.params = params

    condenser.name = 'Condenser'
    condenser.save = True
    condenser.time_step = time_step
    condenser.end_time = end_time

    plant_net.module(condenser)

    #*****************************************************************************
    params['RCIS-shutdown-time'] = -1 * unit.minute
    rcis = Cooler(params)
    rcis.name = 'RCIS'
    rcis.save = True
    rcis.time_step = time_step
    rcis.end_time = end_time

    plant_net.module(rcis)

    #*****************************************************************************
    # Create the BoP network connectivity
    plant_net.connect([reactor, 'coolant-outflow'], [turbine_hp, 'inflow'])
    plant_net.connect([turbine_hp, 'outflow-1'], [turbine_lp1, 'inflow'])
    plant_net.connect([turbine_hp, 'outflow-2'], [turbine_lp2, 'inflow'])
    plant_net.connect([turbine_lp1, 'outflow-1'], [condenser, 'inflow-1'])
    plant_net.connect([turbine_lp2, 'outflow-1'], [condenser, 'inflow-2'])
    plant_net.connect([condenser, 'outflow'], [reactor, 'coolant-inflow'])
    plant_net.connect([reactor, 'RCIS-outflow'], [rcis, 'coolant-inflow'])
    plant_net.connect([rcis, 'coolant-outflow'], [reactor, 'RCIS-inflow'])
    #plant_net.connect([rcis, 'signal-in'], [reactor, 'signal-out'])

    plant_net.draw(engine='dot', node_shape='folder')
    #*****************************************************************************
    # Run network dynamics simulation
    plant.run()

    #*****************************************************************************
    # Plot results

    if plot_results and (plant.use_multiprocessing or plant.rank == 0):

        # Reactor plots
        reactor = plant_net.modules[0]

        (quant, time_unit) = reactor.neutron_phase.get_quantity_history('neutron-dens')
        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']')

        plt.grid()
        plt.savefig('shutdown-neutron-dens.png', dpi=300)

        (quant, time_unit) = reactor.neutron_phase.get_quantity_history('delayed-neutrons-cc')
        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']')

        plt.grid()
        plt.savefig('shutdown-delayed-neutrons-cc.png', dpi=300)

        (quant, time_unit) = reactor.coolant_outflow_phase.get_quantity_history('temp')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']')

        plt.grid()
        plt.savefig('shutdown-coolant-outflow-temp.png', dpi=300)

        (quant, time_unit) = reactor.reactor_phase.get_quantity_history('fuel-temp')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']')
        plt.grid()
        plt.savefig('shutdown-fuel-temp.png', dpi=300)

        # Turbine high pressure plots
        turbine_hp = plant_net.modules[1]

        (quant, time_unit) = turbine_hp.outflow_phase.get_quantity_history('power')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']',
                   title='High Pressure Turbine Power')
        plt.grid()
        plt.savefig('shutdown-turbine-hp-power.png', dpi=300)

        (quant, time_unit) = turbine_hp.outflow_phase.get_quantity_history('temp')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']',
                   title='High Pressure Turbine Outflow Temperature')
        plt.grid()
        plt.savefig('shutdown-turbine-hp-outflow-temp.png', dpi=300)

        # Turbine low pressure graphs
        turbine_lp1 = plant_net.modules[2]

        (quant, time_unit) = turbine_lp1.outflow_phase.get_quantity_history('power')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']',
                   title='Lower Pressure Turbine 1 Power')
        plt.grid()
        plt.savefig('shutdown-turbine-lp1-power.png', dpi=300)

        (quant, time_unit) = turbine_lp1.outflow_phase.get_quantity_history('temp')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']',
                   title='Lower Pressure Turbine 1 Outflow Temperature')
        plt.grid()
        plt.savefig('shutdown-turbine-lp1-outflow-temp.png', dpi=300)

        # Condenser graphs
        condenser = plant_net.modules[4]

        (quant, time_unit) = condenser.outflow_phase.get_quantity_history('temp')

        quant.plot(x_scaling=1/unit.minute, x_label='Time [m]',
                   y_label=quant.latex_name+' ['+quant.unit+']')
        plt.grid()
        plt.savefig('shutdown-condenser-outflow-temp.png', dpi=300)

    # Shutdown The Simulation
    plant.close()

if __name__ == '__main__':
    main()