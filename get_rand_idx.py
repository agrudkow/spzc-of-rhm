from random import gauss

def get_rand_idx(max, cut_off = None):
  cut_off = cut_off if cut_off is not None else max
  
  gen_idx = lambda: int(round(abs(gauss(0, 1) * (max/6))))

  idx = gen_idx()

  while idx >= cut_off:
    idx = gen_idx()

  return(idx)