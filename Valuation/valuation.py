import sys
import numpy as np
import networkx as nx
import datetime
import math
from itertools import product, chain
from collections import namedtuple, defaultdict
from Product.product import (Tolling, EXERCISE_BLOCK, EXERCISE_HALF_HOURLY, 
                     EXERCISE_DAILY, EXERCISE_HOURLY, EXERCISE_BLOCK)

#Period denominations
DAYS_PER_YEAR = 365.242
HOURS_PER_YEAR = 365.242*24
HALF_HOURS_PER_YEAR = 365.242*24*2

#States
STR_ON='on'
STR_OFF='off'
STR_RUP= 'up'
STR_RDN= 'dn'

#Mapping
EXERCISE_TO_FREQ={
    EXERCISE_HALF_HOURLY:(30,'m','HALF_HOURS_PER_YEAR'),
    EXERCISE_HOURLY: (1, 'h', HOURS_PER_YEAR),
    EXERCISE_DAILY: (1, 'D', DAYS_PER_YEAR),
    EXERCISE_BLOCK: '???',
}

IDX_TIMES=0
IDX_DISCOUNT=1
IDX_POWER=2
IDX_FUEL=3
IDX_CARBON=4

#Extended state
ExtState=namedtuple(typename='ExtState',field_names=('state', 'duration', 'restarts' ,'periods'))
ExtState.__repr__ = lambda self: 'es(u={},d={},r={},n={})'.format(
    *list(self._asdict().values())
)

#Valuation policy and cost
PolicyCost = namedtuple('PolicyCost', 'u,q,cost')

class Valuation(object):
    """Valuation of a tolling contract.
    Parameters:
    ----------
    product: Tolling
        The tolling contract to be valued.
    **kwargs:
        state_final_sets the final state (default is OFF)
    State variables:
    ---------------
    State: represented as signed integers; for example for a cycle:
        off: 0
        ramp_up_1:1
        ramp_up_2:2
        on: 3
        ramp_down_1: -1
        off:0
    Duration: positive for on, negative for off, zero for ramp.
    Restarts: increases by 1 when the state changes from off to on.
    Periods: increases by 1 when plant is at any state except off.

    Extended State:
    ---------------
    A tuple of (state, duration, restarts, periods). The notation 
    used is es=(u,d,r,n) 
    with potential indices like u0,d1 indicating u@t=0, d@t=1, etc.

    State transitions:
    ---------------
    For each of the state variable, the respective  transition methods 
    determine the admissable values; the extended state successors are the common of
    these states. This is required for both forward and backward (reverse) directions.

    Active and feasible range for state variables:
    -------------------------------
    If a state variable has no impact in the valuation, this is called an 
    active state, and since is satisfied for any transition, hence it's ignored.
    If, on the other hand, can restrict the plant operating range, a 
    range of admissable values called feasible range is dertermined.    

    Graphs:
    ---------------
    A directed graph is used to determine the admissable states; also used in 
    reverse direction for the same purpose. 
    The extended admissable states are determined using the graph, and 
    in additon duration, restarts, and periods.

    Cost functions:
    ---------------
    The cost function is the sum of switch cost (startup/shutdown), and the 
    payoff functions.

    Intrinsic valuation:
    ---------------
    A dynamic programming approach is used to that starting from 
    the terminal point, iterates all the admissable extended state going 
    backwards, and determines the optimal decision and value going forwards.
    """
    def __init__(self, tolling, **kwargs):
        self.tolling = tolling
        self.start_date=np.datetime64(self.tolling.start_date)
        self.end_date=np.datetime64(self.tolling.end_date)
        #params
        str_final=kwargs.pop('state_final', STR_OFF)
        assert str_final in {STR_OFF, STR_ON}
        self.state_final = 0 if str_final==STR_OFF else max(self._states())
        assert not kwargs, 'Invalid params: {}'.format(kwargs)
        #optim
        self.on_state=self.tolling.plant_params.time.ramp_up+1
        #set up
        self.feasible_periods=len(self._generate_times())
        self.feasible_restarts=self._feasible_restarts()
        self.feasible_min_on, self.feasible_min_off =\
            self._feasible_min_onoff()
        self.state_graph = self._build_state_graph()
        self.state_graph_rev = self.state_graph.reverse(copy=True)

    def feasible_duration(self, xd):
        time_params = self.tolling.plant_params.time
        return -time_params.min_off <= xd <= time_params.min_on
    
    def _feasible_restarts(self):
        #max number of restarts taking into account ramp time
        time_params = self.tolling.plant_params.time
        p = float(self.feasible_periods)
        p /= max(2, time_params.ramp_up, time_params.ramp_down)
        return int(math.ceil(p))
    
    def _feasible_min_onoff(self):
        time_params = self.tolling.plant_params.time
        return [min(self.feasible_periods, xd) for xd in 
                [time_params.min_on, time_params.min_off]]
    
    def _ramp_levels(self):
        time_params = self.tolling.plant_params.time
        return -time_params.ramp_down, time_params.ramp_up
    
    def _states(self):
        rdn, rup=self._ramp_levels()
        return list(range(rdn, rup + 2))
    
    def _to_onoff(self, u):
        return 1 if u == self.on_state else (-1 if u==0 else 0)
    
    def _is_on(self, u):
        return u==self.on_state
    
    @staticmethod
    def _is_off(u):
        return u==0
    
    def _is_ramp(self, u):
        return self._to_onoff(u)==0
    
    def _state_to_str(self, u):
        return ((STR_ON if u>0 else STR_OFF) if self.self._to_onoff(u)
                else '{}{:+}'.format(STR_RUP if u>0 else STR_RDN, u))
    
    def _build_state_graph(self):
        #build the state graph
        g = nx.DiGraph()
        states = self._states()
        nx.add_cycle(g, states)
        nx.add_cycle(g,[0])
        nx.add_cycle(g, [max(states)])
                # for u in self._states():
        #     if self._is_off(u):
        #         G.add_edge(u, u) #stay off
        #         G.add_edge(u, self.on_state) #start up
        #     elif self._is_ramp(u):
        #         G.add_edge(u, u+1 if u>0 else u-1) #ramp up/down
        #     else: #on state
        #         G.add_edge(u, u) #stay on
        #         G.add_edge(u, 0) #shut down
        return g
    
    def _state_successors(self, u, reverse=False):
        assert u in self.state_graph, 'Invalid state: {}; states={}'.format(u, self._states())
        
        graph= self.state_graph_rev if reverse else self.state_graph
        return set(graph.successors(u))

    def _duration_transition(self, d0, u0, u1, reverse):
        #from (d0 at u0), determine {d1} given u1.
        assert self.feasible_duration, 'Invalid duration {}'.format(d0)
        f1=self._to_onoff(u1)
        i_rev = -1 if reverse else 1
        i_same = self._to_onoff(u0)*f1 > 0
        min_off, min_on= self.feasible_min_off, self.feasible_min_on
        if i_same:
            d1=d0+ i_rev*f1
        else:
            dmax= -min_off*self._is_off(u1) + min_on * self._is_on(u1)
            d1= dmax if reverse else f1
        #in the reverse direction, can remain also stay at min_on/min_off
        can_stay_onoff = (reverse and i_same and (-d0==min_off or d0==min_on))
        d1s={d1,d0} if can_stay_onoff else {d1}
        d1s={x for x in d1s if x!=0} if reverse and i_same else d1s
        return {max(-min_off, min(y, min_on)) for y in d1s}
    
    def _restarts_transition(self, r0, u0, u1, reverse):
        #from (r0 at u0), determine {r1} given u1.
        assert r0>=0, 'Invalid restarts; expected positive'
        max_restarts = self.tolling.plant_params.time.max_restarts
        if max_restarts > self.feasible_restarts:
            r1 = self.feasible_restarts
        else:
            u0, u1, i_rev = (u1,u0,-1) if reverse else (u0,u1,1)
            u0, u1 = map(abs, (u0, u1))
            r1 = r0+ i_rev*(u0==0 and u1!=0)
        return r1 if 0<=r1 <= max_restarts else None
    
    def _periods_transition(self, n0, u0, u1, reverse):
        #from (n0 at u0), determine {n1} given u1.
        assert n0>=0, 'Invalid periods; expected positive'
        max_periods = self.tolling.plant_params.time.max_periods
        if max_periods > self.feasible_periods:
            n1 = self.feasible_periods
        else:
            u0, u1, i_rev = (u1,u0,-1) if reverse else (u0,u1,1)
            n1 = n0+i_rev*(u1!=0)
        return n1 if 0<=n1 <= max_periods else None
    
    #build the extended state 
    def _build_ext_state(self, u, d, r, n):
        es0 = ExtState(u, d, r, n)
        assert self._valid_ext_state(es0),'Invalid extended state: {}'.format(
            self._ext_state_to_str(es0))
        return es0
        
    def _ext_state_to_str(self, es):
        return str(es).replace('u', self._state_to_str(es.state))
    
    def _valid_ext_state(self, es):
        u, d, r, n = es
        is_on, is_off = self._is_on(u), self._is_off(u)
        time_params = self.tolling.plant_params.time
        min_periods = d if is_on else abs(u)
        return (
            u in self.state_graph
            and 0 <= r <= time_params.max_restarts
            and min_periods <= n <= time_params.max_periods
            and self.feasible_duration(d)
            and ((is_on and d>0)
                 or (is_off and d<0)
                 or (1-is_on and 1-is_off and d==0))
        )
    
    def _ext_state_transition(self, es0, u1, reverse):
        #from (es0 at u0), determine {es1} given u1.
        r1 = self._restarts_transition(es0.restarts, es0.state, u1, reverse)
        n1 = self._periods_transition(es0.periods, es0.state, u1, reverse)
        es = set()
        if not (r1 is None or n1 is None):
            is_on = self._is_on(u1)
            for d1 in self._duration_transition(es0.duration, es0.state, u1, reverse):
                min_n1 = d1 if self._is_on(u1) else abs(u1)
                if n1 >= min_n1:
                    min_n1 = d1 if is_on else abs(u1)
                    if n1 >= min_n1:
                        es.add(self._build_ext_state(u1, d1, r1, n1))
        return es
    
    def _ext_state_successors(self, es0, reverse=False):
        #from (es0 at u0), determine all admissable {es1} given the direction.
        assert self._valid_ext_state(es0), 'Invalid extended state: {}'.format(es0)
        u0, d0, r0, n0 = es0
        params_time = self.tolling.plant_params.time
        min_off, min_on = self.feasible_min_off, self.feasible_min_on
        successors = set()
        for u1 in self._state_successors(u0, reverse):
            d1s = self._duration_transition(d0, u0, u1, reverse)
            for d1 in d1s:
                if reverse:
                    stay_on = ((d0 > min(1, min_on -1)) 
                               and (d1==1 if min_on ==1 else 1))
                    stay_off = ((-d0 > min(1, min_off-1))
                                and (-d1==1 if min_off ==1 else 1))
                    ind_duration = (u1==u0) if stay_on or stay_off \
                        else (u1!=u0)
                else:
                    stay_on = (d0>0) and (d0+1<=min_on)
                    stay_off = (d0<0) and (d0-1>=-min_off)
                    ind_duration = (u1==u0) if stay_on or stay_off else 1
                r1 = self._restarts_transition(r0, u0, u1, reverse)
                ind_restarts = False
                if r1 is not None:
                    ind_restarts = (0<=r1<=self.feasible_restarts)
                n1 = self._periods_transition(n0, u0, u1, reverse)
                min_n1=d1 if self._is_on(u1) else abs(u1)
                ind_periods = False
                if n1 is not None:
                    ind_periods = (min_n1 <= n1 <= params_time.max_periods)
                if all((ind_duration, ind_restarts, ind_periods)):
                    successors.add(self._build_ext_state(u1, d1, r1, n1))
        return successors
    

    def _switch_cost(self, u0, u1):
        #from u0 and u1, determine the switch cost.
        cost = self.tolling.plant_params.cost
        i_start = self._is_off(u0) and u1==1
        i_shutdown = self._is_on(u0) and u1==min(self._ramp_levels())
        return -cost.startup*i_start - cost.shutdown*i_shutdown
    
    def _optimal_payoff(self, q, u, x_power, x_fuel, x_carbon):
        #for generation levels[q], u and prices, determine opt level and value
        params = self.tolling.plant_params
        if not u:
            q_opt, payoff = 0,0
        else:
            def f_spread(x):
                return x * (x_power -
                           x_fuel/params.capacity.f_efficiency(x)-
                           x_carbon*params.capacity.emissions_factor -
                           params.cost.f_run(x))
            if self._is_on(u):
                q_opt, payoff = self._optimal_payoff_argmax(f_spread, q)
            else:
                q_opt = min(q)
                payoff = f_spread(q_opt)
        return q_opt, payoff
    
    @staticmethod
    def _optimal_payoff_argmax(fun, q):
        #determine the argmax of f over q, and the value at the argmax.
        return max(zip(q, map(fun, q)), key=lambda y: y[-1])
    
    def _cost(self, q, u0, u1, x_power, x_fuel, x_carbon=0):

        #from q, u0, u1 and prices, determine total cost (switch+payoff).
        q_opt, payoff = self._optimal_payoff(q, u0, x_power, x_fuel, x_carbon)
        return q_opt, payoff+ self._switch_cost(u0, u1)
    
    def _generate_times(self, env=None):
        dt, _ = self._freq_tuple()
        start_date = (
            max(self.start_date, np.datetime64(env.pricing_date)) if env 
            else self.start_date
        )
        return np.arange(start_date, self.end_date + 1, step = dt)

    def _freq_tuple(self):
        n, span, n_per_year = EXERCISE_TO_FREQ[self.tolling.exercise_type]
        return np.timedelta64(n, span), n_per_year
    
    def _markets(self):
        #market and market boolean flags for those products
        prd = self.tolling
        mkts = [prd.power_market, prd.fuel_market, prd.carbon_market]
        return list(map(np.array, (mkts, list(map(bool, mkts)))))
    
    def _prices(self, times, env):
        mkts, has_mkts = self._markets()
        prices = np.zeros(shape=(len(times),2+sum(has_mkts)), dtype=np.float64)
        prices[:, IDX_TIMES]=times
        prices[:, IDX_DISCOUNT]=[env.discount_factor(env.currency, y) for 
                                 y in times.astype(datetime.datetime)]
        active_mkts = mkts[has_mkts]
        for t,p in enumerate(times):
            prices[t, IDX_POWER:]=[env.get_price(m,times[t]) for m in active_mkts]
        return prices
    
    def intrinsic(self, env):
        start_date = self.tolling.start_date
        if env.pricing_date > start_date:
            cost, policy, capacity = [0], [], []
        else:
            prices = self._prices(self._generate_times(env), env)
            cost, policy, capacity = self._determine_policy(prices)
        df = env.discount_factor(env.currency, start_date)
        return cost[0]*df, policy, capacity
    
    def _determine_policy(self, prices):
        #determine the optimal policy and cost given the prices.
        #to be implemented
        gen_levels = self.tolling.plant_params.capacity.gen_levels
        nt=len(prices)
        #[time, {es0 -> (u1, q0, cost0)}]
        es_cost = np.empty(shape=nt,dtype=object)

        def empty_policy():
            return PolicyCost(np.iinfo(int).min, -np.inf, -np.inf)
        
        es_cost[-1] = defaultdict(empty_policy)
        #set final admissable states
        for es in self._final_ext_states():
            qf, cost = self._cost(gen_levels, es.state, es.state, *prices[-1, IDX_POWER:])
            es_cost[-1][es]=PolicyCost(es.state, qf, cost)
        dfs=prices[1:,IDX_DISCOUNT]/ prices[:-1,IDX_DISCOUNT]
        #iterate backwards
        for t in reversed(range(nt-1)):
            es0_rev = set(chain(*(self._ext_state_successors(es1, reverse=True)
                                  for es1 in es_cost[t+1])))
            es_cost[t] = defaultdict(empty_policy)

            def _f_cost(_u0, _es1):
                #given u0 and es1, determine cost at 0
                qt, cost_t = self._cost(gen_levels, _u0,
                                        _es1.state, *prices[t,IDX_POWER:])
                return qt, cost_t + dfs[t]*es_cost[t+1][_es1].cost
            
            #populate cost for successors
            for es0 in es0_rev:
                es0_successors = self._ext_state_successors(es0)
                if es0_successors:
                    es_cost[t][es0] = self._policy_argmax(
                        lambda xes1: _f_cost(es0.state, xes1),
                        es0_successors
                    )
        return self._build_policy(nt, es_cost)
    
    @staticmethod
    def _policy_argmax(fun, es):
        es, (q, cost) = max(zip(es, map(fun, es)), key=lambda z: z[1][1])
        return PolicyCost(es.state, q, cost)
    
    def _build_policy(self, nt, es_cost):
        #given es_cost for all transitions and periods, build optimal policy.
        cost, policy, capacity = (np.empty(shape=nt, dtype=d) for d in (float, int, float))
        es0, (u1, capacity[0], cost[0]) = max(es_cost[0].items(), key=lambda x: x[1].cost)
        policy[0]=es0.state
        for t in range(1, nt):
            es0 = self._ext_state_transition(es0, u1, reverse=False).pop()
            policy[t] = es0.state
            u1, capacity[t], cost[t] = es_cost[t][es0]
        return cost, policy, capacity

    def _final_ext_states(self):
        #determine the final admissable extended states.
        rng_duration = self._rng_duration()
        rng_restarts = self._rng_restarts()
        rng_periods = self._rng_periods()
        state = self.state_final
        ext_states=set()
        is_on=self._is_on(state)
        for d, r, n in product(rng_duration[state], rng_restarts, rng_periods):
            if is_on and not n:
                continue
            ext_states.add(self._build_ext_state(state, min(d,n), r, n))
        return ext_states
    
    def _rng_duration(self):
        #range of admissable duration states
        off, on = 0, max(self._states())
        rng_duration = defaultdict(int)
        rng_duration[off] = list(range(-max(self.feasible_min_off,1),0))
        rng_duration[on] = list(range(1, max(self.feasible_min_on+1,2)))
        return rng_duration
    
    def _rng_restarts(self):
        max_restarts = self.tolling.plant_params.time.max_restarts
        active_restarts = max_restarts> self.feasible_restarts
        rng_restarts = ((self.feasible_restarts,) if active_restarts 
                        else list(range(0, max_restarts+1)))
        return rng_restarts
    
    def _rng_periods(self):
        max_periods = self.tolling.plant_params.time.max_periods
        active_periods = max_periods > self.feasible_periods
        rng_periods = ((self.feasible_periods,) if active_periods
                       else list(range(0, max_periods+1)))
        return rng_periods
    