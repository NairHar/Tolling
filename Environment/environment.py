import numpy as np
DAYS_PER_YEAR= 365
class Environment:

    def __init__(self, day, ccy):
        self.pricing_date = day
        self.currency = ccy
        self.dict_ = {}
        
    def add_price(self, mkt, data):
        self.dict_[mkt] = data

    def get_price(self, mkt, tp):
        return self.dict_[mkt][tp]

    def discount_factor(self, ccy, day, **kwargs):
        dt = self.time_in_years(day, **kwargs)
        # return np.exp(-self.price(ccy, contracts=day)*dt)
        return 1
    
    def duration_in_years(self, tfrom, tto, frequency:str='ms', days_per_year=DAYS_PER_YEAR):
        minimum_freq = 'ms'
        min_timedelta = f'timedelta64[{minimum_freq}]'
        used_freq=f'datetime64[{frequency}]'
        used_from=np.datetime64(tfrom, frequency)
        used_to = np.atleast_1d(tto).astype(used_freq)
        day_ms = 3600*24*1000
        shift=0
        dt_freq=(used_to-used_from).astype(min_timedelta).astype(np.float64)
        dt_freq-=shift
        scaling=day_ms*days_per_year
        return dt_freq/scaling
    
    def time_in_years(self, day, **kwargs):
        days_per_year = kwargs.pop('days_per_year', DAYS_PER_YEAR)
        freq='ms'
        dt = self.duration_in_years(self.pricing_date, day, freq, days_per_year=days_per_year)
        return dt[0] if dt.size==1 else dt
    

