# Exact completed public eval cells; static evidence,not a standalone program. Not re-executed.

# completed_s=194.28; raw_code_sha256=e7ca59e67b7d0cf8ae1e6387f851a8a06dee39936241a35571dab134c10f7c87
t0=time.time()
def prove_forward(f):
 zeros={}
 for p,i in zero_witness:
  zeros.update(f.zero_sum(f.row(source.rows[i].name),zeros=zeros,coordinates=[p]))
 pair_row_ids=sorted({i for j,k,p,q in alias_witness for i in p+q})
 reduced=f.rewrite_many([f.row(source.rows[i].name) for i in pair_row_ids],zeros)
 pair_facts=dict(zip(pair_row_ids,reduced))
 defs=dict(zeros)
 for j,k,p,q in alias_witness:
  pos=f.le([(pair_facts[i],1) for i in p],expect=source.var(source.vars[j].name)-source.var(source.vars[k].name))
  neg=f.le([(pair_facts[i],1) for i in q],expect=source.var(source.vars[k].name)-source.var(source.vars[j].name))
  defs[j]=f.eqpair(pos,neg)
 # Both signs available for exact objective obligation matching.
 objective_fact=f.eq([(f.row(r.name),1) for i,r in part_a],expect=source.objective-81)
 f.eq([(objective_fact,-1)])
 f.substitution(defs)
 missing=f.missing()
 print('forward missing',len(missing),[(g.label,g.kind,g.expression.summary(3)) for g in missing[:3]])
 f.complete()
 return defs
f_mi_defs=prove_forward(f_mi)
print('MI forward seconds',round(time.time()-t0,2))

# completed_s=207.358; raw_code_sha256=9f9b7328c2f9edfff63038a3537a62baa670d33195df11d70bf5428088939556
t0=time.time()
# Reverse obligations for deleted rows: exact box witnesses or equality combinations.
def prove_reverse(r):
 # Use unique residual inequalities only, sharing facts across repeated original rows.
 box_keys=set()
 for i in box_rows:
  terms=canonical[i][3]
  key=tuple(sorted((newindex[j],c) for j,c in terms.items()))
  if key and key not in box_keys:
   r.box_le(Expr(0,dict(key))); box_keys.add(key)
 for i,w in equality_dependencies:
  expr=Expr(-source.rows[i].lower,{newindex[j]:c for j,c in canonical[i][3].items()})
  r.eq([(r.row(source.rows[k].name),c) for k,c in w.items()],expect=expr)
 obj=r.eq([(r.row(source.rows[i].name),c) for i,c in objective_witness.items()])
 r.eq([(obj,-1)])
 missing=r.missing()
 print('reverse unique box facts',len(box_keys),'missing',len(missing),[(g.label,g.kind,g.expression.summary(3)) for g in missing[:3]])
 r.complete()
prove_reverse(r_mi)
f_lp_defs=prove_forward(f_lp)
prove_reverse(r_lp)
print('remaining proof seconds',round(time.time()-t0,2))
