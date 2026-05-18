import numpy as np
import datetime
from datetime import timedelta
from Valuation.valuation import Valuation, Tolling, STR_OFF, STR_ON
from Product.product import LOAD_BASE, EXERCISE_DAILY, Tolling, PlantParameters
import pandas as pd
from Environment.environment import Environment

GBP = 'gbp'

def build_tolling(t0,t1, gen_levels, power, gas, carbon,
                  efficiency, exercise_type,  ramp_up, ramp_down, 
                  min_on, min_off, max_restarts, max_periods, startup, shutdown, running):
    return Tolling(
        t0, t1, exercise_type, LOAD_BASE, 
        PlantParameters(gen_levels, efficiency, ramp_up=ramp_up, ramp_down=ramp_down,
                        min_off=min_off, min_on=min_on, max_restarts=max_restarts, 
                        max_periods=max_periods, startup=startup, shutdown=shutdown, 
                        running=running),
                        power, gas, carbon
    )

def build_date(yr, mn, day):
    return datetime.datetime(yr, mn, day, 0, 0, 0)

def build_date_rng(t0, t1, dt):
    nt0, nt1 = map(np.datetime64, (t0,t1))
    return np.arange(nt0, nt1+1, step=dt)


def build_env(day, power_args, gas_args,ir=0.0):
    power, power_crv = power_args
    gas, gas_crv = gas_args
    env = Environment(day, GBP)
    rng = pd.date_range(day, periods=365)
    if isinstance(power_crv, pd.Series):
        p = power_crv
    else:
        p = pd.Series(power_crv, index=rng)
    if isinstance(gas_crv, pd.Series):
        g= gas_crv
    else:
        g=pd.Series(gas_crv, index=rng)

    env.add_price(power, p)
    env.add_price(gas,g)

    return env

'''Set up'''
t0 = build_date(2014, 1, 1)

t1=t0+ timedelta(days=10)
nper=10
exercise_type = EXERCISE_DAILY
cases=[(STR_OFF, nper-1), (STR_ON, nper)]

env = build_env(t0, ('power', 90), ('gas',100))

tolling = build_tolling(t0, t1, [100], 'power', 'gas', None,
                        efficiency=0.4, exercise_type=exercise_type, ramp_up=2, ramp_down=3,
                        min_on=1, min_off=1, max_restarts=999, max_periods=999,
                        startup=25, shutdown=15, running=5)
ss, k = cases[0]
v1, p1, _ = Valuation(tolling, state_final=ss).intrinsic(env)
print (v1)