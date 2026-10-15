# Exact completed public eval cell; static evidence, not a standalone program. Not re-executed.
# raw_code_sha256=802bcb130628601666a20a4eb56df75ac445193a2ba468571a13de5df71471ff
# Forward maps require only the fixed-coordinate equality to rewrite objective/inverse identities.
for label,b in [('MI',f_mi),('LP',f_lp)]:
 t=time.time(); b.substitution({'x154978':b.row('c277594')}); b.complete()
 print(label,'forward complete',round(time.time()-t,2))
# Backward maps reconstruct every original row. All redundancy premises are retained.
for label,b in [('MI',r_mi),('LP',r_lp)]:
 t=time.time()
 rowfacts={name:b.row(name) for name in {rn for w in ramp_witnesses for rn,m in w['rows']} | {w['eq'] for w in initial_witnesses} | {w['edge'] for w in initial_witnesses}}
 lowerfacts={name:b.lower(name) for name in {vn for w in ramp_witnesses for vn,m in w['lower_bounds']} | {vn for w in initial_witnesses for vn,m in w['lower_bounds']}}
 for w in ramp_witnesses:
  premises=[(rowfacts[rn],m) for rn,m in w['rows']]+[(lowerfacts[vn],m) for vn,m in w['lower_bounds']]
  fact=b.le(premises)
  b.check('row.upper['+w['row']+']',fact)
 for w in initial_witnesses:
  fact=b.le([(rowfacts[w['eq']],w['eq_multiplier']),(rowfacts[w['edge']],w['edge_multiplier'])]+[(lowerfacts[vn],m) for vn,m in w['lower_bounds']])
  b.check('row.upper['+w['row']+']',fact)
 b.complete()
 print(label,'reverse complete',round(time.time()-t,2))
print('all four claims complete')
