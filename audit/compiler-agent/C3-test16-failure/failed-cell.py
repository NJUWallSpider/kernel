# Proof construction helpers, kept alive and saved later as runnable code.
proof_helpers = r'''
def box_fact(b, expression):
    """Prove caller-selected LE using the exact independent variable box."""
    expression=Expr.coerce(expression);terms=[];residual=expression.constant
    for i,a in expression.terms.items():
        v=b.model.vars[i]
        bound=v.upper if a>0 else v.lower
        assert bound is not None, (v.name,expression)
        terms.append((b.upper(i) if a>0 else b.lower(i),abs(a)))
        residual+=a*bound
    assert residual<=0, (residual,expression)
    return b.le(terms,constant=residual,expect=expression)

def rewrite_selected(b, fact, definitions):
    hits=[(definitions[i],-a) for i,a in fact.expression.terms.items() if i in definitions]
    return b.lin(fact.kind,[(fact,1),*hits]) if hits else fact

def fill_missing(b, definitions=None, box=False):
    missing=b.missing()
    kinds=Counter(g.kind for g in missing)
    print('missing',b.index,len(missing),dict(kinds),[(g.label,str(g.expression)) for g in missing[:3]])
    for g in missing:
        if g.kind=='Eq' and definitions is not None:
            terms=[];residual=g.expression
            for i,a in g.expression.terms.items():
                if i in definitions:
                    terms.append((definitions[i],a));residual-=a*definitions[i].expression
            assert residual==Expr(0),(g.label,residual)
            b.check(g.label,b.eq(terms,expect=g.expression))
        elif g.kind=='Le' and box:
            b.check(g.label,box_fact(b,g.expression))
        else:raise AssertionError(('Unsupported proof obligation',g.label,g.kind,str(g.expression)))
    b.complete()

def exact_stage_proof(source,target,events,elim,agg_order,agg_rows,allrepl,box_redundant):
    p=Proof(source,target)
    fwd={v.name:source.var(v.name) for v in target.vars}
    rename={i:target.var(source.vars[i].name) for i in range(len(source.vars)) if i not in allrepl}
    rev={v.name:allrepl[i].substitute(rename) if i in allrepl else target.var(v.name) for i,v in enumerate(source.vars)}
    for integer_domain in (True,False):
        f,r=p.bijection(fwd,rev,integers=integer_domain)
        initial={}
        for event in events:
            kind=event['kind']
            if kind=='bound_fixed':
                i=event['pivot'];initial[i]=f.eqpair(f.upper(i),f.lower(i));continue
            rowfact=f.row(event['row'])
            normal=rewrite_selected(f,rowfact,initial)
            assert normal.expression==event['normal']
            if kind=='zero':
                pivots=event['pivots'];sign=1 if next(iter(normal.expression.terms.values()))>0 else -1
                for i in pivots:
                    ai=sign*normal.expression.coefficient(i)
                    terms=[(normal,Fraction(sign,1)/ai)]
                    terms.extend((f.lower(k),sign*a/ai) for k,a in normal.expression.terms.items() if k!=i)
                    upper=f.le(terms,expect=source.var(i))
                    initial[i]=f.eqpair(upper,f.lower(i))
            elif kind in ('fixed','alias'):
                i=event['pivot'];a=normal.expression.coefficient(i)
                initial[i]=f.eq([(normal,1/a)],expect=source.var(i)-elim[i])
            else:raise AssertionError(kind)
        definitions=dict(initial)
        # Finalize base aliases if their retained root is later an aggregate pivot.
        def final_definition(i):
            fact=definitions[i]
            desired=source.var(i)-allrepl[i]
            if fact.expression!=desired:
                terms=[(fact,1)]
                for k,a in elim[i].terms.items():
                    assert k in definitions and k!=i
                    terms.append((definitions[k],a))
                fact=f.eq(terms,expect=desired);definitions[i]=fact
            return fact
        for i in agg_order:
            j=agg_rows[i];rf=f.row(j);terms=[(rf,1)]
            for k,a in rf.expression.terms.items():
                if k!=i and k in definitions:
                    terms.append((final_definition(k),-a))
            a=rf.expression.coefficient(i)
            definitions[i]=f.eq([(fact,coef/a) for fact,coef in terms],expect=source.var(i)-allrepl[i])
        for i in allrepl:final_definition(i)
        # Rewrite all changed retained rows, not an assumed row pattern.
        for tr in target.rows:
            sr=source.row(tr.name)
            for side in ('Eq',) if sr.equality else tuple(side for side,bd in [('Lower',sr.lower),('Upper',sr.upper)] if bd is not None):
                rewrite_selected(f,f.row(sr.name,side=side),definitions)
        # Objective and both inverse compositions: explicit sums of proved identities.
        fill_missing(f,definitions=definitions)
        # Every reconstructed original bound has already been box-audited.
        # Deleted box-redundant rows require the same explicit bound combinations.
        fill_missing(r,box=True)
        print('exact claims completed',integer_domain,'forward steps',len(f.steps),'reverse steps',len(r.steps))
    return p
'''
exec(proof_helpers)
start=time.time()
proofA=exact_stage_proof(source,modelA,events,elim,agg_order,agg_rows,allrepl,box_redundant)
print('proof A authored seconds',round(time.time()-start,2))
