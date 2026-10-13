//! Independent copied-map oracle for the candidate Facts abstraction.
//! Include as a test-only child of verify; no production verifier changes.
use super::{Fact,Facts};
use crate::model::{Expr,Q};
use crate::proof::Kind;
use std::collections::BTreeMap;

#[derive(Clone,Debug)]
struct Value{kind:Kind,number:i64}
type Reference=BTreeMap<u32,Value>;

fn key(i:usize)->u32{match i{32=>u32::MAX,33=>u32::MAX-1,_=>i as u32}}
fn fact(value:&Value)->Fact{Fact{kind:value.kind,expr:Expr{constant:Q::from_integer(value.number.into()),terms:vec![]}}}
fn assert_same(scope:&Facts<'_>,reference:&Reference){
    assert_eq!(scope.len(),reference.len(),"logical live count");
    for i in 0..34{let id=key(i);let (actual,probes)=scope.lookup(&id);assert!(probes>=1);match (actual,reference.get(&id)){
        (Some(f),Some(v))=>{assert_eq!(f.kind,v.kind,"kind at {id}");assert_eq!(f.expr.constant,Q::from_integer(v.number.into()),"value at {id}");assert!(f.expr.terms.is_empty());},
        (None,None)=>{},_=>panic!("visibility differs at {id}: actual {}, expected {}",actual.is_some(),reference.contains_key(&id)),
    }}
}
fn define(scope:&mut Facts<'_>,reference:&mut Reference,id:u32,value:Value,limit:usize)->bool{
    let expected=!reference.contains_key(&id)&&reference.len()<limit;
    let actual=scope.lookup(&id).0.is_none()&&scope.len()<limit;
    assert_eq!(actual,expected,"Context insertion preconditions");
    if actual{scope.try_reserve(1).unwrap();scope.insert(id,fact(&value));reference.insert(id,value);}
    assert_same(scope,reference);actual
}
fn erase(scope:&mut Facts<'_>,reference:&mut Reference,id:u32)->bool{
    let expected=reference.remove(&id).is_some();let (actual,probes)=scope.remove(&id).unwrap();assert!(probes>=1);assert_eq!(actual,expected,"DROP decision for {id}");assert_same(scope,reference);actual
}
struct Random(u64);
impl Random{fn next(&mut self)->u64{self.0^=self.0<<13;self.0^=self.0>>7;self.0^=self.0<<17;self.0}}
#[derive(Default)]struct Counts{operations:u64,defines:u64,drops:u64,forks:u64,rejections:u64}

fn random_scope(mut scope:Facts<'_>,mut reference:Reference,rng:&mut Random,depth:usize,fuel:&mut usize,counts:&mut Counts){
    assert_same(&scope,&reference);
    for _ in 0..24{
        if *fuel==0{return;}
        *fuel-=1;counts.operations+=1;let operation=rng.next()%16;let id=key((rng.next()%34) as usize);
        match operation{
            0..=5=>{let value=Value{kind:match rng.next()%3{0=>Kind::Le,1=>Kind::Eq,_=>Kind::Int},number:rng.next() as i32 as i64};counts.defines+=1;if !define(&mut scope,&mut reference,id,value,12){counts.rejections+=1;}},
            6..=10=>{counts.drops+=1;if !erase(&mut scope,&mut reference,id){counts.rejections+=1;}},
            11..=13=>{assert_eq!(scope.lookup(&id).0.is_some(),reference.contains_key(&id));},
            _ if depth<12=>{
                counts.forks+=2;
                // Every reference child is a complete independent map copy.
                random_scope(scope.fork(),reference.clone(),rng,depth+1,fuel,counts);
                assert_same(&scope,&reference);
                random_scope(scope.fork(),reference.clone(),rng,depth+1,fuel,counts);
                assert_same(&scope,&reference);
            },
            _=>{},
        }
        assert_same(&scope,&reference);
    }
}

#[test]
fn copied_map_oracle_128_seeded_state_trees(){
    let mut counts=Counts::default();
    for seed in 1..=128u64{
        let mut rng=Random(0x52505853434f5045^seed.wrapping_mul(0x9e3779b97f4a7c15));
        let mut scope=Facts::new();let mut reference=Reference::new();
        for i in 0..8{define(&mut scope,&mut reference,key(i),Value{kind:Kind::Eq,number:seed as i64*100+i as i64},12);}
        random_scope(scope,reference,&mut rng,0,&mut 1024,&mut counts);
    }
    println!("scope oracle: seed base=0x52505853434f5045, traces=128, operations={}, defines={}, drops={}, child_forks={}, expected_rejections={}",counts.operations,counts.defines,counts.drops,counts.forks,counts.rejections);
    assert!(counts.operations>50_000);assert!(counts.forks>1_000);assert!(counts.rejections>10_000);
}

#[test]
fn inherited_drop_reuse_and_second_drop_never_resurrect_ancestors(){
    let mut root=Facts::new();let mut original=Reference::new();define(&mut root,&mut original,7,Value{kind:Kind::Eq,number:11},8);
    {
        let mut child=root.fork();let mut expected=original.clone();
        assert!(erase(&mut child,&mut expected,7));assert!(!erase(&mut child,&mut expected,7));
        assert!(define(&mut child,&mut expected,7,Value{kind:Kind::Int,number:22},8));
        {
            let mut grandchild=child.fork();let mut copy=expected.clone();
            assert!(erase(&mut grandchild,&mut copy,7));assert!(define(&mut grandchild,&mut copy,7,Value{kind:Kind::Le,number:33},8));
            assert!(erase(&mut grandchild,&mut copy,7));assert!(grandchild.lookup(&7).0.is_none());
        }
        assert_same(&child,&expected);assert!(erase(&mut child,&mut expected,7));
        assert!(define(&mut child,&mut expected,7,Value{kind:Kind::Eq,number:44},8));assert!(erase(&mut child,&mut expected,7));
        assert!(child.lookup(&7).0.is_none());assert_same(&root,&original);
    }
    assert_same(&root.fork(),&original);
    assert!(erase(&mut root,&mut original,7));assert!(define(&mut root,&mut original,7,Value{kind:Kind::Le,number:55},8));
}

#[test]
fn nested_mask_then_local_definition_drop_remains_hidden(){
    let mut root=Facts::new();let mut original=Reference::new();define(&mut root,&mut original,3,Value{kind:Kind::Eq,number:1},8);
    let mut child=root.fork();let mut expected=original.clone();erase(&mut child,&mut expected,3);
    let mut grandchild=child.fork();let mut copy=expected.clone();
    assert!(define(&mut grandchild,&mut copy,3,Value{kind:Kind::Int,number:2},8));
    assert!(erase(&mut grandchild,&mut copy,3));assert!(!erase(&mut grandchild,&mut copy,3));
    assert!(grandchild.lookup(&3).0.is_none());assert_same(&child,&expected);assert_same(&root,&original);
}

fn deep_scope(scope:&Facts<'_>,reference:&Reference,depth:usize){
    if depth==64{let (_,probes)=scope.lookup(&u32::MAX);assert_eq!(probes,2*(depth+1));return;}
    let mut child=scope.fork();let mut copy=reference.clone();
    let id=(depth%16) as u32;
    erase(&mut child,&mut copy,id);
    define(&mut child,&mut copy,id,Value{kind:Kind::Eq,number:depth as i64},32);
    deep_scope(&child,&copy,depth+1);
    assert_same(&child,&copy);assert_same(scope,reference);
}

#[test]
fn sixty_four_ancestor_scopes_keep_counts_masks_and_probe_costs(){
    let mut root=Facts::new();let mut reference=Reference::new();
    for i in 0..16{define(&mut root,&mut reference,i,Value{kind:Kind::Eq,number:100+i as i64},32);}
    deep_scope(&root,&reference,0);assert_same(&root,&reference);
}

#[test]
fn every_ancestor_lookup_probe_is_reported(){
    let mut root=Facts::new();let mut reference=Reference::new();define(&mut root,&mut reference,1,Value{kind:Kind::Eq,number:1},8);
    assert_eq!(root.lookup(&1).1,1);assert_eq!(root.lookup(&2).1,2);
    let mut child=root.fork();assert_eq!(child.lookup(&1).1,3);assert_eq!(child.lookup(&2).1,4);
    {let grandchild=child.fork();assert_eq!(grandchild.lookup(&1).1,5);assert_eq!(grandchild.lookup(&2).1,6);}
    let (removed,probes)=child.remove(&1).unwrap();assert!(removed);assert_eq!(probes,4);assert_eq!(child.lookup(&1).1,2);
    child.insert(1,fact(&Value{kind:Kind::Le,number:2}));assert_eq!(child.lookup(&1).1,1);
    let (removed,probes)=child.remove(&1).unwrap();assert!(removed);assert_eq!(probes,2);assert!(child.lookup(&1).0.is_none());
}

#[test]
fn whole_split_right_can_consume_unchanged_parent_after_left_fork(){
    let mut scope=Facts::new();let mut original=Reference::new();for i in 0..8{define(&mut scope,&mut original,i,Value{kind:Kind::Eq,number:i as i64},12);}
    {let mut left=scope.fork();let mut left_reference=original.clone();erase(&mut left,&mut left_reference,1);define(&mut left,&mut left_reference,1,Value{kind:Kind::Int,number:99},12);erase(&mut left,&mut left_reference,2);}
    assert_same(&scope,&original);
    let mut right=scope;let mut right_reference=original;assert!(erase(&mut right,&mut right_reference,1));
    assert!(define(&mut right,&mut right_reference,1,Value{kind:Kind::Le,number:-5},12));assert_same(&right,&right_reference);
}

#[test]
fn logical_limit_and_duplicate_insert_guards_match_copied_maps(){
    let mut root=Facts::new();let mut reference=Reference::new();
    assert!(!define(&mut root,&mut reference,0,Value{kind:Kind::Eq,number:0},0));
    for i in 0..4{assert!(define(&mut root,&mut reference,i,Value{kind:Kind::Eq,number:i as i64},4));}
    assert!(!define(&mut root,&mut reference,9,Value{kind:Kind::Eq,number:9},4));
    let mut child=root.fork();let mut copied=reference.clone();assert!(!define(&mut child,&mut copied,0,Value{kind:Kind::Int,number:99},8));
    erase(&mut child,&mut copied,0);assert!(define(&mut child,&mut copied,9,Value{kind:Kind::Le,number:9},4));
    assert!(!define(&mut child,&mut copied,0,Value{kind:Kind::Eq,number:0},4));assert_same(&root,&reference);
}
