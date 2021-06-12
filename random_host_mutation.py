from get_rand_idx import get_rand_idx
from random import shuffle

from generate_all_ips import generate_all_ips


class RandomHostMutation():
  def __init__(self, host_ips, all_v_ips):
    self.host_ips = host_ips
    self.all_v_ips = all_v_ips
    # Shuffle all avaliable ips on the initialization
    shuffle(self.all_v_ips)

    self.v_ips = dict()
    self.r_ips = dict()

    self.init_mutation()

  def init_mutation(self):
    v_ips_len = len(self.all_v_ips)
    host_ips_len = len(self.host_ips)

    for host_ip in self.host_ips:
      idx = get_rand_idx(v_ips_len - host_ips_len)
      v_ip = self.all_v_ips[idx]

      self.v_ips[v_ip] = host_ip
      self.r_ips[host_ip] = v_ip

      del self.all_v_ips[idx]

  def mutate(self):
    v_ips_len = len(self.all_v_ips)
    host_ips_len = len(self.host_ips)
    total_len = v_ips_len - host_ips_len

    # Clear v_ips
    self.v_ips.clear()

    for i, r_ip in enumerate(self.r_ips):
      # i is used to account for addition and removal of ips
      idx = get_rand_idx(total_len - i)
      v_ip = self.all_v_ips[idx]

      old_v_ip =  self.r_ips[r_ip]

      self.v_ips[v_ip] = r_ip
      self.r_ips[r_ip] = v_ip

      self.all_v_ips.append(old_v_ip)
      del self.all_v_ips[idx]

    return (self.r_ips, self.v_ips)

  def get_v_ips(self):
    return self.v_ips

  def get_r_ips(self):
    return self.r_ips



if __name__ == "__main__":
  r_ips = [
    '10.0.0.251', 
    '10.0.0.252'
  ]

  v_ips = [ip for ip in generate_all_ips('10.0.0.4', '10.0.1.0') if ip not in r_ips]

  rm = RandomHostMutation(r_ips, v_ips, 10)

  print('R_IPS: {}'.format(rm.get_r_ips()))
  print('V_IPS: {}'.format(rm.get_v_ips()))

  rm.mutate()

  print('R_IPS: {}'.format(rm.get_r_ips()))
  print('V_IPS: {}'.format(rm.get_v_ips()))