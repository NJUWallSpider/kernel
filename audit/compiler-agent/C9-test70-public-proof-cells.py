# Static evidence excerpt from the completed C9 test70 compiler Agent.
# These are exact public eval cells, in order, operating in the Agent's persistent
# authoring namespace. This excerpt is not a standalone executable proof.
# No cell was re-executed for this audit. The original immutable session.jsonl
# and the per-cell raw-code SHA-256 values bind the supplied witness program.

# Public cell completed at 246.381s: Declaring complete correctness relation
# raw_code_sha256=2a27ce26c2d1993253dfbc207b8d2a52ca6e8f650e63a1c48f11c4047d7beb86
agg_by_rep={js[0]:js for js in agg_groups}
fmap={v.name:(Expr(0,{j:Fraction(1) for j in agg_by_rep[source.var_index[v.name]]}) if source.var_index[v.name] in agg_by_rep else source.var(v.name)) for v in target.vars}
rmap={v.name:(replacements[v.name] if v.name in replacements else target.var(v.name)) for v in source.vars}
observations=[(v.name,v.name) for v in target.vars if source.var_index[v.name] not in agg_by_rep]
proof=Proof(source,target)
f,r=proof.correspondence(fmap,rmap,projection=observations)
rlp=proof.claim(reverse=True,mapping=rmap,integers=False,objective='Equal',projection=observations)
print(proof.contract_summary(max_items=2))
# Model facts are re-used once; no repeated incidence construction.
f_packfacts={}
for t,(k,c,S) in enumerate(packings):
 rowfact=f.row(source.rows[k].name)
 f_packfacts[t]=f.le([(rowfact,1),(f.upper(source.vars[c].name),1)]) if c is not None else f.le([(rowfact,1)])
# c1201 plus x122<=1 forces x121>=1, and conversely.
fixedfacts={}
for j,otherj in [(forced[0],forced[1]),(forced[1],forced[0])]:
 lower_one=f.le([(f.row('c1201'),Fraction(1,20)),(f.upper(source.vars[otherj].name),1)],expect=1-source.var(source.vars[j].name))
 fixedfacts[source.vars[j].name]=f.eqpair(f.upper(source.vars[j].name),lower_one)
# Rewrite retained rows affected by the two fixed coordinates.
f.substitution(fixedfacts)
print('forward missing count',len(f.missing()),[(g.label,g.kind,g.expression.summary(2)) for g in f.missing()[:4]])
print('reverse missing count',len(r.missing()),[(g.label,g.kind,g.expression.summary(2)) for g in r.missing()[:4]])

# Public cell completed at 410.776s: Proving aggregation and binary strengthening
# raw_code_sha256=3df95c6750fe169d153c3b792670a164608db2d7248b033b2bc2299b36bf14a9
pack_by_row={k:t for t,(k,c,S) in enumerate(packings)}
for js in agg_groups:
 repname=source.vars[js[0]].name
 lower=f.box_le(Expr(0,{j:Fraction(-1) for j in js}))
 t=pack_by_row[agg_witness[js[0]]]
 subset=set(js)
 upper=f.le([(f_packfacts[t],1)]+[(f.lower(source.vars[j].name),1) for j in packings[t][2]-subset],expect=Expr(-1,{j:Fraction(1) for j in js}))
 f.check('variable.lower['+repname+']',lower);f.check('variable.upper['+repname+']',upper)
f_obj_delta=target.objective.substitute({i:fmap[v.name] for i,v in enumerate(target.vars)})-source.objective
objfact=f.le([(f.lower(source.vars[j].name),obj[j]) for j in sorted(freevars)]+[(fixedfacts[source.vars[j].name],-obj.get(j,0)) for j in forced],expect=f_obj_delta)
f.check('objective.non_increasing',objfact)
print('aggregation bounds and objective proved')
# Preserve full cover witness coverage, not just a displayed sample.
cover_cost=sum(sum(len(packings[t][2]) if t is not None else 1 for t,g in covers[source.row_index[name]][1]) for name in tighten)
print('cover expanded bound terms',cover_cost)
t0=time.time();gatefacts={}
for name,(c,M,U) in tighten.items():
 k=source.row_index[name];groups=covers[k][1];multiplicities=Counter();premises=[]
 for t,subset in groups:
  if t is None:
   j=subset[0];premises.append((f.upper(source.vars[j].name),1));multiplicities[j]+=1
  else:
   premises.append((f_packfacts[t],1));multiplicities.update(packings[t][2])
 P={j for j,a in source.rows[k].expr.terms.items() if a==1}
 for j,n in multiplicities.items():
  excess=n-(1 if j in P else 0)
  assert excess>=0
  if excess:premises.append((f.lower(source.vars[j].name),excess))
 global_bound=f.le(premises,expect=Expr(-U,{j:Fraction(1) for j in P}))
 goal=Expr(0,{**{j:Fraction(1) for j in P},c:Fraction(-U)})
 old=f.row(name)
 fact=f.cases(source.var(source.vars[c].name),kind='Le',expect=goal,
   left=lambda b,a,old=old,M=M,U=U,goal=goal:b.le([(old,1),(a,M-U)],expect=goal),
   right=lambda b,a,global_bound=global_bound,U=U,goal=goal:b.le([(global_bound,1),(a,U)],expect=goal))
 gatefacts[name]=fact;f.check('row.upper['+name+']',fact)
print('tightened gate certificates built',len(gatefacts),'seconds',round(time.time()-t0,2))
print('forward missing',[(g.label,g.kind,g.expression.summary(2)) for g in f.missing()[:5]])

# Public cell completed at 474.704s: Completing reverse maps and final artifact
# raw_code_sha256=9738d4468e258502f4da8c981a453fb918e9bf5dd45b356d31312f22fb556f76
t0=time.time()
for rev in (r,rlp):
 for g in rev.missing():
  if g.label.startswith('row.upper['):
   name=g.label[len('row.upper['):-1]
   if name in tighten:
    c,M,U=tighten[name]
    fact=rev.le([(rev.row(name),1),(rev.lower(source.vars[c].name),M-U)],expect=g.expression)
   else:
    assert name in {source.rows[k].name for k in leafrows}|{'c1200'}
    fact=rev.box_le(g.expression)
   rev.check(g.label,fact)
  else:raise RuntimeError((g.label,g.expression.summary()))
 print('reverse',rev is r,'missing',len(rev.missing()))
f.complete();r.complete();rlp.complete()
print('all claims complete',round(time.time()-t0,2))
with open('output/contract_preview.json','w') as fh:json.dump(proof.contract_summary(),fh,indent=2)
# One final commitment; serialize precisely the target proved above.
target.write_mps('output/reformulated.mps')
print('committed bytes',os.path.getsize('output/reformulated.mps'))

# Public cell completed at 537.869s: Compressing witnesses without changing target
# raw_code_sha256=272cd123b5eff18d81baed5c297a47125dfca01b4f93138a0e0559372c51a9d1
# Preserve the concrete failed call before changing only proof elaboration.
compile_failure={'call':"proof.verify('output', committed_model='output/reformulated.mps')",'status':'RESOURCE_LIMIT','message':'input file bytes','certificate_bytes':os.path.getsize('output/certificate.json'),'target_unchanged':True}
with open('output/initial_compile_failure.json','w') as fh:json.dump(compile_failure,fh,indent=2)
# Distinct demanded subset bounds, per original packing row.
subset_needs=defaultdict(set)
for name in tighten:
 for t,subset in covers[source.row_index[name]][1]:
  if t is not None:subset_needs[t].add(frozenset(subset))
for js in agg_groups:
 subset_needs[pack_by_row[agg_witness[js[0]]]].add(frozenset(js))
print('distinct subset facts',sum(map(len,subset_needs.values())), 'full naive cost',sum(len(packings[t][2])-len(S) for t,sets in subset_needs.items() for S in sets))
# Build exact subset-containment parent witnesses. This is combinatorial bookkeeping, not optimization.
subset_parents={};naive_cost=0;parent_cost=0
for t,sets in subset_needs.items():
 root=frozenset(packings[t][2]);known=[root]
 for S in sorted(sets,key=lambda S:(-len(S),tuple(sorted(S)))):
  if S==root:continue
  parent=min((T for T in known if S<=T),key=lambda T:len(T))
  subset_parents[t,S]=parent
  parent_cost+=len(parent)-len(S);naive_cost+=len(root)-len(S)
  known.append(S)
print('parent cancellation cost',parent_cost,'vs',naive_cost)
print('existing certificate MB',os.path.getsize('output/certificate.json')/1e6)

# Public cell completed at 581.138s: Factoring repeated cancellation certificates
# raw_code_sha256=f0ef372f1bab9a85a26428927c0c9fb99056386feebac81c99ad2b2439599b79
def interval_chunks(indices):
 xs=sorted(indices);chunks=[]
 if not xs:return chunks
 start=prev=xs[0]
 def add_run(a,b):
  while a<b:
   length=(a & -a) if a else 1 << ((b-a).bit_length()-1)
   while length>b-a:length//=2
   chunks.append((a,length));a+=length
 for j in xs[1:]:
  if j==prev+1:prev=j
  else:add_run(start,prev+1);start=prev=j
 add_run(start,prev+1)
 return chunks
chunks_total=sum(len(interval_chunks(T-S)) for (t,S),T in subset_parents.items())
print('dyadic cancellation refs',chunks_total,'vs coordinate refs',parent_cost)
print('largest demanded subset',max(len(S) for sets in subset_needs.values() for S in sets))
os.makedirs('output/initial_compile_failure',exist_ok=True)
os.replace('output/certificate.json','output/initial_compile_failure/certificate.json')
compile_failure['preserved_certificate']='output/initial_compile_failure/certificate.json'
with open('output/initial_compile_failure.json','w') as fh:json.dump(compile_failure,fh,indent=2)
# Retain all mathematical/model/witness data; discard only the oversized failed proof object.
del proof,f,r,rlp,f_packfacts,gatefacts,fixedfacts,fact,lower,upper,objfact,global_bound,old
import gc
gc.collect()
proof=Proof(source,target)
f,r=proof.correspondence(fmap,rmap,projection=observations)
rlp=proof.claim(reverse=True,mapping=rmap,integers=False,objective='Equal',projection=observations)
print('fresh proof with unchanged contract and target')

# Public cell completed at 730.201s: Authoring shared exact subset witnesses
# raw_code_sha256=ff83e058180287c732e466570643ea00266d83a85353b9e75ccb6e0797e82c83
t0=time.time()
f_packfacts={}
for t,(k,c,S) in enumerate(packings):
 rowfact=f.row(source.rows[k].name)
 f_packfacts[t]=f.le([(rowfact,1),(f.upper(c),1)]) if c is not None else f.le([(rowfact,1)])
fixedfacts={}
for j,otherj in [(forced[0],forced[1]),(forced[1],forced[0])]:
 lower_one=f.le([(f.row('c1201'),Fraction(1,20)),(f.upper(otherj),1)],expect=1-source.var(source.vars[j].name))
 fixedfacts[source.vars[j].name]=f.eqpair(f.upper(j),lower_one)
f.substitution(fixedfacts)
# Shared exact nonnegativity facts for dyadic coordinate intervals.
dyadic_facts={}
def lower_interval(a,n):
 if n==1:return f.lower(a)
 key=(a,n)
 if key not in dyadic_facts:
  dyadic_facts[key]=f.le([(lower_interval(a,n//2),1),(lower_interval(a+n//2,n//2),1)])
 return dyadic_facts[key]
def lower_subset(S):
 return [(lower_interval(a,n),1) for a,n in interval_chunks(S)]
subset_facts={}
for t,sets in subset_needs.items():
 root=frozenset(packings[t][2]);subset_facts[t,root]=f_packfacts[t]
 for S in sorted(sets,key=lambda S:(-len(S),tuple(sorted(S)))):
  if S==root:continue
  parent=subset_parents[t,S]
  subset_facts[t,S]=f.le([(subset_facts[t,parent],1)]+lower_subset(parent-S),expect=Expr(-1,{j:Fraction(1) for j in S}))
for js in agg_groups:
 name=source.vars[js[0]].name
 low=f.le(lower_subset(js),expect=Expr(0,{j:Fraction(-1) for j in js}))
 up=subset_facts[pack_by_row[agg_witness[js[0]]],frozenset(js)]
 f.check('variable.lower['+name+']',low);f.check('variable.upper['+name+']',up)
objfact=f.le([(f.lower(j),obj[j]) for j in sorted(freevars)]+[(fixedfacts[source.vars[j].name],-obj.get(j,0)) for j in forced],expect=f_obj_delta)
f.check('objective.non_increasing',objfact)
for name,(c,M,U) in tighten.items():
 k=source.row_index[name];groups=covers[k][1]
 premises=[((f.upper(subset[0]) if t is None else subset_facts[t,frozenset(subset)]),1) for t,subset in groups]
 P={j for j,a in source.rows[k].expr.terms.items() if a==1}
 bound=f.le(premises,expect=Expr(-U,{j:Fraction(1) for j in P}))
 goal=Expr(0,{**{j:Fraction(1) for j in P},c:Fraction(-U)})
 old=f.row(name)
 fact=f.cases(source.var(source.vars[c].name),kind='Le',expect=goal,
  left=lambda b,a,old=old,M=M,U=U,goal=goal:b.le([(old,1),(a,M-U)],expect=goal),
  right=lambda b,a,bound=bound,U=U,goal=goal:b.le([(bound,1),(a,U)],expect=goal))
 f.check('row.upper['+name+']',fact)
for rev in (r,rlp):
 for g in rev.missing():
  name=g.label[len('row.upper['):-1]
  if name in tighten:
   c,M,U=tighten[name];fact=rev.le([(rev.row(name),1),(rev.lower(source.vars[c].name),M-U)],expect=g.expression)
  else:fact=rev.box_le(g.expression)
  rev.check(g.label,fact)
f.complete();r.complete();rlp.complete()
print('refactored proof complete','seconds',round(time.time()-t0,2),'subset facts',len(subset_facts),'dyadic facts',len(dyadic_facts))
print('preflight',proof.preflight())
