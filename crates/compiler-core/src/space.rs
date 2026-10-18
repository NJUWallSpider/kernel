//! Authoring identities. They are never serialized into trusted artifacts.
use kernel_core::model::Expr;
use std::sync::{
    Arc, RwLock,
    atomic::{AtomicU64, Ordering},
};

static NEXT: AtomicU64 = AtomicU64::new(1);

#[derive(Debug)]
pub struct Space {
    pub id: u64,
    pub name: String,
    pub parent: Option<Arc<Space>>,
    names: RwLock<Vec<String>>,
}

impl Space {
    pub fn new(name: String, names: Vec<String>, parent: Option<Arc<Space>>) -> Arc<Self> {
        Arc::new(Self {
            id: NEXT.fetch_add(1, Ordering::Relaxed),
            name,
            parent,
            names: RwLock::new(names),
        })
    }
    pub fn add_name(&self, name: String) {
        self.names.write().expect("space names poisoned").push(name);
    }
    pub fn name_at(&self, index: u32) -> String {
        self.names
            .read()
            .expect("space names poisoned")
            .get(index as usize)
            .cloned()
            .unwrap_or_else(|| format!("?{index}"))
    }
    pub fn contains(&self, other: &Space) -> bool {
        self.id == other.id || self.parent.as_ref().is_some_and(|p| p.contains(other))
    }
}

#[derive(Clone, Debug)]
pub struct BoundExpr {
    pub value: Arc<Expr>,
    pub space: Option<Arc<Space>>,
}

impl BoundExpr {
    pub fn new(value: Expr, space: Option<Arc<Space>>) -> Self {
        let mut space = if value.terms.is_empty() { None } else { space };
        while let Some(parent) = space.as_ref().and_then(|s| s.parent.clone()) {
            if value.terms.iter().any(|(i, _)| {
                *i as usize >= parent.names.read().expect("space names poisoned").len()
            }) {
                break;
            }
            space = Some(parent);
        }
        Self {
            value: Arc::new(value),
            space,
        }
    }
    pub fn in_space(&self, target: &Space) -> Result<(), crate::error::Error> {
        if let Some(source) = &self.space {
            if !target.contains(source) {
                return Err(crate::error::Error::Coordinate(format!(
                    "expression belongs to space {} ({}), but scope uses space {} ({})",
                    source.id, source.name, target.id, target.name
                )));
            }
        }
        Ok(())
    }
    pub fn combined_space(&self, other: &Self) -> Result<Option<Arc<Space>>, crate::error::Error> {
        match (&self.space, &other.space) {
            (None, b) => Ok(b.clone()),
            (a, None) => Ok(a.clone()),
            (Some(a), Some(b)) if a.contains(b) => Ok(Some(a.clone())),
            (Some(a), Some(b)) if b.contains(a) => Ok(Some(b.clone())),
            (Some(a), Some(b)) => Err(crate::error::Error::Coordinate(format!(
                "cannot combine space {} ({}): {} with space {} ({}): {}",
                a.id,
                a.name,
                pretty(&self.value, Some(a)),
                b.id,
                b.name,
                pretty(&other.value, Some(b))
            ))),
        }
    }
}

pub fn pretty(e: &Expr, space: Option<&Space>) -> String {
    use num_traits::{One, Signed, Zero};
    let mut out = String::new();
    let mut append = |negative: bool, term: String| {
        if out.is_empty() {
            if negative {
                out.push('-');
            }
        } else {
            out.push_str(if negative { " - " } else { " + " });
        }
        out.push_str(&term);
    };
    if !e.constant.is_zero() {
        append(e.constant.is_negative(), e.constant.abs().to_string());
    }
    for (i, q) in e.terms.iter().take(20) {
        let name = space
            .map(|s| s.name_at(*i))
            .unwrap_or_else(|| format!("v[{i}]"));
        let magnitude = q.abs();
        append(
            q.is_negative(),
            if magnitude.is_one() {
                name
            } else {
                format!("{magnitude}*{name}")
            },
        );
    }
    if e.terms.len() > 20 {
        out.push_str(&format!(" + … ({} more terms)", e.terms.len() - 20));
    }
    if out.is_empty() {
        out.push('0');
    }
    out
}
