# Exact completed public cells; static evidence, not a standalone program. Not re-executed.

# completed_s=227.828; raw_code_sha256=4b50bab8fad02e267dddc79e198964d6fca3380548b8a59f7150273d0452627f
opt_ids=[next(iter(e.terms)) for e in opts]
all_menu_indices=set(range(302))
option_lowers=[mi_scope.lower(e) for e in opts]
def subset_expr(indices):
 return Expr(0,{opt_ids[k]:1 for k in indices})
def prove_subset(indices):
 indices=set(indices)
 e=subset_expr(indices)
 lo=mi_scope.le([(option_lowers[k],1) for k in sorted(indices)],expect=-e)
 hi=mi_scope.le([(menu.sum,1)]+[(option_lowers[k],1) for k in sorted(all_menu_indices-indices)],expect=e-1)
 return e,lo,hi
A,Alo,Ahi=prove_subset(range(222))
p_exprs=[]; subset_witness=[]
for g in range(221):
 ks=[k for k,level in enumerate(levels) if level['p_count']>g]
 e,lo,hi=prove_subset(ks)
 p_exprs.append(e)
 subset_witness.append({'p_group':g,'menu_indices':ks})
mi_map={v.name:Expr(point_min[v.name]) for v in source.vars}
for g,names in enumerate(p_groups):mi_map[names[0]]=p_exprs[g]
for j in range(8,16):mi_map[b_names[j]]=1-A
# Exact objective identity under reconstruction.
mi_obj=source.objective.substitute({j:mi_map[v.name] for j,v in enumerate(source.vars)})
mi_scope.eq([(menu.moment,1),(menu.sum,-80)],expect=mi_obj-mi_scope.model.var('objective_value'))
mi_scope.le([(Ahi,80)],constant=-310,expect=80*A-390)
mi_scope.le([(Ahi,80)],constant=-61,expect=80*A-141)
missing=r_mi.missing(scope=mi_scope, mapping=mi_map) if 'scope' in inspect.signature(r_mi.missing).parameters else None
print('missing signature',inspect.signature(r_mi.missing))
r_mi.complete(scope=mi_scope,mapping=mi_map)
print('integer reverse complete')


# completed_s=236.564; raw_code_sha256=258c8fa38ed9a672dc6e86ed09fe4e3b6fb53ce7eac6ec241aa9fcb6502c3f95
print('menu equations',menu.sum.expression.summary(),menu.moment.expression.summary())
print('current b(8) map',mi_map['b(8)'].summary())
print('intended b(8): 1 for menu 0..221, 0 for 222..301')
# Correct the reconstruction map before completing or committing its proof.
for j in range(8,16):mi_map[b_names[j]]=A
mi_obj=source.objective.substitute({j:mi_map[v.name] for j,v in enumerate(source.vars)})
mi_scope.eq([(menu.moment,1),(menu.sum,-80)],expect=mi_obj-mi_scope.model.var('objective_value'))
mi_scope.le([(Ahi,80)],constant=-310,expect=80*A-390)
mi_scope.le([(Ahi,80)],constant=-61,expect=80*A-141)
r_mi.complete(scope=mi_scope,mapping=mi_map)
print('integer reverse complete')

