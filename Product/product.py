import sys
import numpy as np
import itertools
from Descriptors.descriptors import(ArrayProperty, CallableProperty,FloatProperty, DateTimeProperty, EnumProperty,
                                    TypedProperty)

#Constants
EXERCISE_HALF_HOURLY= 'HALF_HOURLY'
EXERCISE_HOURLY = 'HOURLY'
EXERCISE_DAILY = 'DAILY'
EXERCISE_BLOCK = 'BLOCK'
LOAD_BASE = 'BASE'
LOAD_PEAK = 'PEAK'
LOAD_EXT_PEAK = 'EXT_PEAK'

class Capacity():
    gen_levels = ArrayProperty('gen_levels', dtype=float, ndim=1)
    f_efficiency = CallableProperty('f_efficiency', allow_scalar=True)
    emissions_factor = FloatProperty('emissions_factor', positive=True )
    f_ramp_rate = CallableProperty('f_ramp_rate', allow_scalar=True)

    def __init__(self, gen_levels, efficiency, emissions_factor, ramp_rate):
        self.gen_levels = gen_levels
        if any(self.gen_levels < 0):
            msg = 'gen_levels must be non-negative, but found gen_levels={}'.format(self.gen_levels)
            raise ValueError(msg)
        
        self.f_efficiency = efficiency
        self.emissions_factor = emissions_factor
        if not ramp_rate:
            ramp_rate= np.max(gen_levels)

        self.f_ramp_rate = ramp_rate

class Time:
    """
    Time-related parameters (the unit is assumed to be the operating
    time unit of the plant; hours or days for example).
    
    Parameters:
    ----------
    min_on=IntegerProperty('min_on', positive=True)
    min_off=IntegerProperty('min_off', positive=True)
    ramp_up=IntegerProperty('ramp_up', positive=True)
    ramp_down=IntegerProperty('ramp_down', positive=True)
    max_restarts=IntegerProperty('max_restarts', positive=True)
    max_periods=IntegerProperty('max_periods', positive=True)
    """
    def __init__(self, min_on, min_off, ramp_up, ramp_down, max_restarts, max_periods):
        self.min_on = min_on
        self.min_off = min_off
        self.ramp_up = ramp_up
        self.ramp_down = ramp_down
        self.max_restarts = max_restarts
        self.max_periods = max_periods      

class Cost:
    """
    Cost-related parameters (in ccy per unit of energy; like prices)
    Parameters:
    ----------
    startup:float
        Startup cost
    shutdown:float
        Shutdown cost
    run: float| Callable Property
        Running cost: either a function of one arguement (capacity) or a fixed number.
    """

    def __init__(self, startup,shutdown, running):
        self.startup = startup
        self.shutdown = shutdown
        self.running = running


class PlantParameters:
    """
    Plant parameters used in the tolling product.
    Parameters:
    ----------
    gen_levels: array of floats
        Minimum generating capacity.
    efficiency:float|callableProperty
        Efficiency: either a function of one arguement (capacity) or a fixed number.
    kwargs:keyword arguments, optional
        All the rest of capacity, time and cost parameters.
    """
    def __init__(self, gen_levels, efficiency, **kwargs):
        self.capacity = Capacity(gen_levels, efficiency, 
                                 kwargs.pop('emissions_factor', 1.0), 
                                 kwargs.pop('ramp_rate', np.max(gen_levels))
                                 )
        self.time=Time(
            kwargs.pop('min_on', 1),
            kwargs.pop('min_off', 1),
            kwargs.pop('ramp_up', 0),
            kwargs.pop('ramp_down', 0),
            kwargs.pop('max_restarts', sys.maxsize),
            kwargs.pop('max_periods', sys.maxsize)  
        )

        self.cost = Cost(
            *[kwargs.pop(a,d) for a, d in 
              [
            ('startup', 0),
            ('shutdown', 0),
            ('running', 0)
            ]]
        )

class Tolling:
    """
    Tolling product parameters.
    Parameters:
    ----------
    start_date: datetime
        Start date of the tolling product.
    end_date: datetime
        End date of the tolling product.
    exercise_type: enum['HOURLY', 'DAILY', 'BLOCK']
        the type of allowed exercise of the tolling product. It can be one of the following:
        'HOURLY', 'DAILY', 'BLOCK'.
    load_type: enum['BASE', 'PEAK', 'EXT_PEAK']
        the load type of the generation.
    power_market: object
        An instance of the power market class that contains the power market parameters.
    fuel_market: object
        An instance of the fuel market class that contains the fuel market parameters.
    carbon_market: object
        An instance of the carbon market class that contains the carbon market parameters.
    """
    start_date=DateTimeProperty('start_date')
    end_date=DateTimeProperty('end_date')
    exercise_type=EnumProperty('exercise_type', 
                               [EXERCISE_HALF_HOURLY, EXERCISE_HOURLY, EXERCISE_DAILY, EXERCISE_BLOCK])
    load_type = EnumProperty(
        'load_type',
        [LOAD_BASE, LOAD_PEAK, LOAD_EXT_PEAK]
    )
    plant_params = TypedProperty('parameters', PlantParameters)
    def __init__(self, start_date, end_date, exercise_type, load_type, params,
                 power_market, fuel_market, carbon_market=None):
        self.start_date = start_date
        self.end_date = end_date
        self.exercise_type = exercise_type
        self.load_type = load_type
        self.plant_params = params
        self.power_market = power_market
        self.fuel_market = fuel_market
        self.carbon_market = carbon_market

class Cost:
    startup = FloatProperty('startup', positive=True)
    shutdown = FloatProperty('shutdown', positive=True)
    f_run = CallableProperty('f_run', allow_scalar=True)

    def __init__(self, startup, shutdown, running):
        self.startup = startup
        self.shutdown = shutdown
        self.f_run = running

    def __eq__(self, other):
        if type(other)==type(self):
            return (self.startup==other.startup
                    and self.shutdown==other.shutdown
                    and all(self.f_run(x)==other.f_run(x) 
                            for x in np.linspace(0, 1000, 100)))
        return False
        

