def author_forward(b):
    zfacts={}
    for ri,sign,fresh in zsteps:
        row=source.rows[ri]; rf=b.row(row.name)
        iseq=row.lower==row.upper
        already=[(i,a) for i,a in row.expr.terms.items() if i in zfacts]
        assert len(already)+len(fresh)==len(row.expr.terms)
        if len(fresh)==1 and iseq:
            i=fresh[0]; a=row.expr.coefficient(i)
            zfacts[i]=b.eq([(rf,1/a)]+[(zfacts[j],-c/a) for j,c in already])
        else:
            # Normalize the chosen row side to sum positive_coeff*x <= 0.
            row_mult=sign if iseq else 1
            for i in fresh:
                a=sign*row.expr.coefficient(i)
                terms=[(rf,Fraction(row_mult,1)/a)]
                terms.extend((zfacts[j],-sign*c/a) for j,c in already)
                terms.extend((b.lower(source.vars[j].name),sign*row.expr.coefficient(j)/a) for j in fresh if j!=i)
                le=b.le(terms)
                zfacts[i]=b.eqpair(le,b.lower(source.vars[i].name))
    assert set(zfacts)==zcoords
    definitions=dict(zfacts)
    for i,q in fixed.items():
        if i not in definitions:
            definitions[i]=b.eqpair(b.upper(source.vars[i].name),b.lower(source.vars[i].name))
    for i,j in aliases.items():
        row=source.rows[alias_row[i]];a=row.expr.coefficient(i)
        terms=[(b.row(row.name),1/a)]
        terms.extend((zfacts[k],-c/a) for k,c in row.expr.terms.items() if k in zfacts)
        assert set(row.expr.terms)-set(zfacts)=={i,j}
        definitions[i]=b.eq(terms)
    b.substitution(definitions)
    return definitions
