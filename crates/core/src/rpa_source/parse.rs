//! A bounded source-language frontend. It only expands syntax into the existing
//! JSON Certificate schema; the ordinary decoder and kernel remain authoritative.

use crate::model::{Q, check_q, parse_q};
use num_traits::{One, Zero};
use serde_json::{Map, Number, Value};
use std::collections::{BTreeMap, HashMap};

use super::{MAX_EXPANDED_NODES, MAX_SOURCE_BYTES, MAX_SOURCE_DEPTH};

#[derive(Clone, Copy)]
struct Location {
    line: usize,
    column: usize,
}

impl Location {
    fn invalid(self, message: impl std::fmt::Display) -> String {
        format!(
            "INVALID RPA source line {}:{}: {message}",
            self.line, self.column
        )
    }
    fn resource(self, message: impl std::fmt::Display) -> String {
        format!(
            "RESOURCE_LIMIT RPA source line {}:{}: {message}",
            self.line, self.column
        )
    }
    fn wrap(self, message: String) -> String {
        if message.starts_with("RESOURCE_LIMIT") {
            self.resource(
                message
                    .trim_start_matches("RESOURCE_LIMIT")
                    .trim_start_matches(':')
                    .trim(),
            )
        } else {
            self.invalid(message)
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
enum TokenKind {
    Ident(String),
    Number(String),
    String(String),
    Punct(char),
    Eof,
}

#[derive(Clone)]
struct Token {
    kind: TokenKind,
    location: Location,
}

struct Lexer<'a> {
    text: &'a str,
    offset: usize,
    location: Location,
}

impl<'a> Lexer<'a> {
    fn new(text: &'a str) -> Self {
        Self {
            text,
            offset: 0,
            location: Location { line: 2, column: 1 },
        }
    }
    fn peek(&self) -> Option<char> {
        self.text[self.offset..].chars().next()
    }
    fn advance(&mut self) -> Option<char> {
        let ch = self.peek()?;
        self.offset += ch.len_utf8();
        if ch == '\n' {
            self.location.line += 1;
            self.location.column = 1;
        } else {
            self.location.column += 1;
        }
        Some(ch)
    }
    fn next(&mut self) -> Result<Token, String> {
        loop {
            while self.peek().is_some_and(char::is_whitespace) {
                self.advance();
            }
            if self.text[self.offset..].starts_with("//") {
                while self.peek().is_some_and(|ch| ch != '\n') {
                    self.advance();
                }
                continue;
            }
            if self.text[self.offset..].starts_with("/*") {
                let start = self.location;
                self.advance();
                self.advance();
                loop {
                    if self.text[self.offset..].starts_with("*/") {
                        self.advance();
                        self.advance();
                        break;
                    }
                    if self.advance().is_none() {
                        return Err(start.invalid("unterminated block comment"));
                    }
                }
                continue;
            }
            break;
        }
        let location = self.location;
        let start = self.offset;
        let Some(ch) = self.peek() else {
            return Ok(Token {
                kind: TokenKind::Eof,
                location,
            });
        };
        let kind = if ch.is_ascii_alphabetic() || ch == '_' {
            self.advance();
            while self
                .peek()
                .is_some_and(|c| c.is_ascii_alphanumeric() || c == '_')
            {
                self.advance();
            }
            TokenKind::Ident(self.text[start..self.offset].into())
        } else if ch.is_ascii_digit()
            || (ch == '.' && self.text[self.offset + 1..].starts_with(|c: char| c.is_ascii_digit()))
        {
            while self.peek().is_some_and(|c| c.is_ascii_digit()) {
                self.advance();
            }
            if self.peek() == Some('.') {
                self.advance();
                while self.peek().is_some_and(|c| c.is_ascii_digit()) {
                    self.advance();
                }
            }
            if self
                .peek()
                .is_some_and(|c| matches!(c, 'e' | 'E' | 'd' | 'D'))
            {
                self.advance();
                if self.peek().is_some_and(|c| matches!(c, '+' | '-')) {
                    self.advance();
                }
                while self.peek().is_some_and(|c| c.is_ascii_digit()) {
                    self.advance();
                }
            }
            TokenKind::Number(self.text[start..self.offset].into())
        } else if ch == '"' {
            self.advance();
            let mut escaped = false;
            loop {
                let Some(c) = self.advance() else {
                    return Err(location.invalid("unterminated string"));
                };
                if !escaped && c == '"' {
                    break;
                }
                if !escaped && c == '\\' {
                    escaped = true;
                } else {
                    escaped = false;
                }
            }
            let value: String = serde_json::from_str(&self.text[start..self.offset])
                .map_err(|e| location.invalid(format!("invalid string: {e}")))?;
            TokenKind::String(value)
        } else if "{}[]():,;=+-*/.".contains(ch) {
            self.advance();
            TokenKind::Punct(ch)
        } else {
            return Err(location.invalid(format!("unexpected character {ch:?}")));
        };
        Ok(Token { kind, location })
    }
}

#[derive(Clone)]
enum Tag {
    Plain,
    Coordinate(u32),
    Reference,
    Scalar(Q),
    Expression,
}

#[derive(Clone)]
struct Node {
    value: Value,
    nodes: usize,
    depth: usize,
    bytes: usize,
    tag: Tag,
}

struct Parser<'a> {
    lexer: Lexer<'a>,
    token: Token,
    aliases: HashMap<String, Node>,
    used_nodes: usize,
    used_bytes: usize,
}

pub(super) struct Document {
    pub certificate: Value,
    pub models: Option<Value>,
}

#[cfg(test)]
fn parse_body(body: &str) -> Result<Value, String> {
    parse_document(body).map(|document| document.certificate)
}

pub(super) fn parse_document(body: &str) -> Result<Document, String> {
    let mut lexer = Lexer::new(body);
    let token = lexer.next()?;
    let mut parser = Parser {
        lexer,
        token,
        aliases: HashMap::new(),
        used_nodes: 0,
        used_bytes: 0,
    };
    let mut models = None;
    while parser.ident_is("let") || parser.ident_is("models") {
        if parser.ident_is("models") {
            let location = parser.token.location;
            if models.is_some() {
                return Err(location.invalid("duplicate models declaration"));
            }
            parser.bump()?;
            models = Some(parser.object(1)?.value);
            parser.take(';')?;
            continue;
        }
        parser.bump()?;
        let location = parser.token.location;
        let name = parser.ident()?;
        if reserved(&name) {
            return Err(location.invalid(format!("reserved alias name {name:?}")));
        }
        if parser.aliases.contains_key(&name) {
            return Err(location.invalid(format!("duplicate alias {name:?}")));
        }
        parser.expect('=')?;
        let value = parser.value(1)?;
        parser.expect(';')?;
        parser
            .aliases
            .try_reserve(1)
            .map_err(|_| location.resource("alias allocation"))?;
        parser.aliases.insert(name, value);
    }
    let location = parser.token.location;
    if !parser.ident_is("certificate") {
        return Err(location.invalid("expected certificate { ... }"));
    }
    parser.bump()?;
    let result = parser.object(1)?;
    parser.take(';')?;
    if parser.token.kind != TokenKind::Eof {
        return Err(parser
            .token
            .location
            .invalid("unexpected content after certificate"));
    }
    Ok(Document {
        certificate: result.value,
        models,
    })
}

impl Parser<'_> {
    fn bump(&mut self) -> Result<Token, String> {
        let next = self.lexer.next()?;
        Ok(std::mem::replace(&mut self.token, next))
    }
    fn ident_is(&self, name: &str) -> bool {
        matches!(&self.token.kind, TokenKind::Ident(value) if value == name)
    }
    fn ident(&mut self) -> Result<String, String> {
        if let TokenKind::Ident(name) = &self.token.kind {
            let name = name.clone();
            self.bump()?;
            Ok(name)
        } else {
            Err(self.token.location.invalid("expected identifier"))
        }
    }
    fn take(&mut self, ch: char) -> Result<bool, String> {
        if self.token.kind == TokenKind::Punct(ch) {
            self.bump()?;
            Ok(true)
        } else {
            Ok(false)
        }
    }
    fn expect(&mut self, ch: char) -> Result<(), String> {
        if self.take(ch)? {
            Ok(())
        } else {
            Err(self.token.location.invalid(format!("expected {ch:?}")))
        }
    }
    fn depth(&self, depth: usize) -> Result<(), String> {
        if depth > MAX_SOURCE_DEPTH {
            Err(self.token.location.resource("nesting depth"))
        } else {
            Ok(())
        }
    }
    fn charge(&mut self, count: usize) -> Result<(), String> {
        self.used_nodes = self
            .used_nodes
            .checked_add(count)
            .filter(|n| *n <= MAX_EXPANDED_NODES)
            .ok_or_else(|| self.token.location.resource("expanded node budget"))?;
        Ok(())
    }
    fn charge_bytes(&mut self, count: usize) -> Result<(), String> {
        self.used_bytes = self
            .used_bytes
            .checked_add(count)
            .filter(|n| *n <= MAX_SOURCE_BYTES)
            .ok_or_else(|| {
                self.token
                    .location
                    .resource("expanded byte allocation budget")
            })?;
        Ok(())
    }
    fn node(&mut self, value: Value, tag: Tag) -> Result<Node, String> {
        let (nodes, depth, bytes) = shape(&value);
        self.charge(nodes)?;
        self.charge_bytes(bytes)?;
        Ok(Node {
            value,
            nodes,
            depth,
            bytes,
            tag,
        })
    }
    fn insert_depth(&self, node: &Node, depth: usize) -> Result<(), String> {
        if depth.saturating_add(node.depth).saturating_sub(1) > MAX_SOURCE_DEPTH {
            Err(self.token.location.resource("expanded nesting depth"))
        } else {
            Ok(())
        }
    }
    fn alias(&mut self, name: &str, depth: usize) -> Result<Node, String> {
        let node = self.aliases.get(name).ok_or_else(|| {
            self.token
                .location
                .invalid(format!("undefined alias {name:?}"))
        })?;
        self.insert_depth(node, depth)?;
        let count = node.nodes;
        let bytes = node.bytes;
        self.charge(count)?;
        self.charge_bytes(bytes)?;
        Ok(self.aliases[name].clone())
    }
    fn object(&mut self, depth: usize) -> Result<Node, String> {
        self.depth(depth)?;
        self.expect('{')?;
        self.charge(1)?;
        self.charge_bytes(2)?;
        let mut values = Map::new();
        let mut nodes = 1;
        let mut max_depth = 1;
        let mut bytes = 2;
        while self.token.kind != TokenKind::Punct('}') {
            let location = self.token.location;
            let field = self.field_name(depth)?;
            if values.contains_key(&field) {
                return Err(location.invalid(format!("duplicate field {field:?}")));
            }
            let overhead = string_bytes(&field) + 1 + usize::from(!values.is_empty());
            self.charge_bytes(overhead)?;
            if !(field == "checks" && self.token.kind == TokenKind::Punct('{')) {
                self.expect(':')?;
            }
            let child = self.value(depth + 1)?;
            nodes += child.nodes;
            max_depth = max_depth.max(child.depth + 1);
            bytes += overhead + child.bytes;
            values.insert(field, child.value);
            if self.take(',')? || self.take(';')? {
                continue;
            }
            if self.token.kind != TokenKind::Punct('}') {
                return Err(self.token.location.invalid("expected ',' or '}'"));
            }
        }
        self.expect('}')?;
        Ok(Node {
            value: Value::Object(values),
            nodes,
            depth: max_depth,
            bytes,
            tag: Tag::Plain,
        })
    }
    fn field_name(&mut self, depth: usize) -> Result<String, String> {
        let location = self.token.location;
        let mut name = match self.bump()?.kind {
            TokenKind::String(value) => return Ok(value),
            TokenKind::Ident(value) => value,
            _ => return Err(location.invalid("expected record field name")),
        };
        let mut parts = 0;
        loop {
            if self.take('.')? {
                parts += 1;
                self.depth(depth + parts)?;
                name.push('.');
                name.push_str(&self.ident()?);
            } else if self.take('[')? {
                parts += 1;
                self.depth(depth + parts)?;
                name.push('[');
                let index_location = self.token.location;
                match self.bump()?.kind {
                    TokenKind::Number(number) if number.bytes().all(|c| c.is_ascii_digit()) => {
                        let index = number
                            .parse::<u32>()
                            .map_err(|_| index_location.invalid("obligation index out of range"))?;
                        name.push_str(&index.to_string());
                    }
                    TokenKind::String(value) => {
                        name.push_str(
                            &serde_json::to_string(&value)
                                .map_err(|e| index_location.invalid(e))?,
                        );
                    }
                    _ => {
                        return Err(index_location
                            .invalid("expected obligation index or quoted model name"));
                    }
                }
                self.expect(']')?;
                name.push(']');
            } else {
                break;
            }
        }
        Ok(name)
    }
    fn array(&mut self, depth: usize, closing: char) -> Result<Node, String> {
        self.depth(depth)?;
        self.bump()?;
        self.charge(1)?;
        self.charge_bytes(2)?;
        let mut values = Vec::new();
        let mut nodes = 1;
        let mut max_depth = 1;
        let mut bytes = 2;
        while self.token.kind != TokenKind::Punct(closing) {
            let splice = matches!(&self.token.kind, TokenKind::Ident(name) if expansion(name));
            let child = self.value(depth + 1)?;
            if splice {
                let Value::Array(items) = child.value else {
                    unreachable!()
                };
                let separator = usize::from(!values.is_empty() && !items.is_empty());
                self.charge_bytes(separator)?;
                values
                    .try_reserve(items.len())
                    .map_err(|_| self.token.location.resource("array allocation"))?;
                nodes += child.nodes - 1;
                max_depth = max_depth.max(child.depth);
                bytes += child.bytes - 2 + separator;
                values.extend(items);
            } else {
                let separator = usize::from(!values.is_empty());
                self.charge_bytes(separator)?;
                values
                    .try_reserve(1)
                    .map_err(|_| self.token.location.resource("array allocation"))?;
                nodes += child.nodes;
                max_depth = max_depth.max(child.depth + 1);
                bytes += child.bytes + separator;
                values.push(child.value);
            }
            if self.take(',')? {
                continue;
            }
            if self.token.kind != TokenKind::Punct(closing) {
                return Err(self
                    .token
                    .location
                    .invalid(format!("expected ',' or {closing:?}")));
            }
        }
        self.expect(closing)?;
        Ok(Node {
            value: Value::Array(values),
            nodes,
            depth: max_depth,
            bytes,
            tag: Tag::Plain,
        })
    }
    fn value(&mut self, depth: usize) -> Result<Node, String> {
        self.depth(depth)?;
        let location = self.token.location;
        let node = match self.token.kind.clone() {
            TokenKind::Punct('{') => self.object(depth)?,
            TokenKind::Punct('[') => self.array(depth, ']')?,
            TokenKind::Punct('(') => self.array(depth, ')')?,
            TokenKind::String(value) => {
                self.bump()?;
                self.node(Value::String(value), Tag::Plain)?
            }
            TokenKind::Number(text) => {
                self.bump()?;
                if !text.bytes().all(|c| c.is_ascii_digit()) {
                    return Err(location.invalid(
                        "bare numbers must be unsigned integers; use q(...) for exact scalars",
                    ));
                }
                let n = text
                    .parse::<u64>()
                    .map_err(|_| location.invalid("unsigned integer out of range"))?;
                self.node(Value::Number(Number::from(n)), Tag::Plain)?
            }
            TokenKind::Ident(name) => {
                self.bump()?;
                self.named_value(name, depth, location)?
            }
            _ => return Err(location.invalid("expected source value")),
        };
        self.insert_depth(&node, depth)?;
        Ok(node)
    }
    // Keep the generic recursive value frame small: the arithmetic and builtin
    // dispatch has substantially larger debug-build temporaries.
    fn named_value(
        &mut self,
        name: String,
        depth: usize,
        location: Location,
    ) -> Result<Node, String> {
        match name.as_str() {
            "true" => self.node(Value::Bool(true), Tag::Plain),
            "false" => self.node(Value::Bool(false), Tag::Plain),
            "null" => self.node(Value::Null, Tag::Plain),
            "exact" => self.node(Value::String("Exact".into()), Tag::Reference),
            "q" => self.scalar_value(depth),
            "expr" => self.expression_value(depth),
            "lin" => self.lin(depth),
            "round" => self.round(depth),
            "drop" => self.drop_step(depth),
            _ if reference_builtin(&name).is_some() => self.reference(&name, depth),
            _ if expansion(&name) => self.expand(&name, depth),
            _ if coordinate_name(&name).is_some() => self.coordinate_value(&name, location),
            _ if fact_name(&name).is_some() => self.fact_value(&name, location),
            _ if self.aliases.contains_key(&name) => self.alias(&name, depth),
            _ if variant(&name) => self.variant_value(name, depth),
            _ => Err(location.invalid(format!("undefined alias or source construct {name:?}"))),
        }
    }
    fn scalar_value(&mut self, depth: usize) -> Result<Node, String> {
        self.expect('(')?;
        let expression = self.arithmetic(Context::Scalar, depth + 1)?;
        self.expect(')')?;
        self.node(
            Value::String(expression.constant.to_string()),
            Tag::Scalar(expression.constant),
        )
    }
    fn expression_value(&mut self, depth: usize) -> Result<Node, String> {
        self.expect('(')?;
        let expression = self.arithmetic(Context::Coordinates, depth + 1)?;
        self.expect(')')?;
        self.expr_node(expression)
    }
    fn coordinate_value(&mut self, name: &str, location: Location) -> Result<Node, String> {
        let id = coordinate_name(name)
            .unwrap()
            .parse::<u32>()
            .map_err(|_| location.invalid("coordinate ID out of range"))?;
        self.node(Value::Number(Number::from(id)), Tag::Coordinate(id))
    }
    fn fact_value(&mut self, name: &str, location: Location) -> Result<Node, String> {
        let id = fact_name(name)
            .unwrap()
            .parse::<u32>()
            .map_err(|_| location.invalid("local fact ID out of range"))?;
        self.ref_node("Local", id)
    }
    fn variant_value(&mut self, mut name: String, mut depth: usize) -> Result<Node, String> {
        let mut wrappers = Vec::new();
        let mut node = loop {
            if self.token.kind == TokenKind::Punct('{') {
                let payload = self.object(depth + 1)?;
                break self.wrap_variant(name, payload)?;
            }
            if !self.take('(')? {
                break self.node(Value::String(name), Tag::Plain)?;
            }
            wrappers
                .try_reserve(1)
                .map_err(|_| self.token.location.resource("variant wrapper allocation"))?;
            wrappers.push(name);
            depth += 1;
            self.depth(depth)?;
            if let TokenKind::Ident(next) = &self.token.kind {
                if variant(next) {
                    name = self.ident()?;
                    continue;
                }
            }
            break self.value(depth)?;
        };
        for name in wrappers.into_iter().rev() {
            self.expect(')')?;
            node = self.wrap_variant(name, node)?;
        }
        Ok(node)
    }
    fn wrap_variant(&mut self, name: String, payload: Node) -> Result<Node, String> {
        self.charge(1)?;
        let bytes = string_bytes(&name) + 3 + payload.bytes;
        self.charge_bytes(bytes - payload.bytes)?;
        let mut values = Map::new();
        values.insert(name, payload.value);
        Ok(Node {
            value: Value::Object(values),
            nodes: payload.nodes + 1,
            depth: payload.depth + 1,
            bytes,
            tag: Tag::Plain,
        })
    }
    fn unsigned(&mut self, depth: usize) -> Result<u32, String> {
        let location = self.token.location;
        let node = self.value(depth)?;
        node.value
            .as_u64()
            .and_then(|n| u32::try_from(n).ok())
            .ok_or_else(|| location.invalid("expected unsigned 32-bit ID"))
    }
    fn register(&mut self, depth: usize) -> Result<u32, String> {
        let location = self.token.location;
        let node = self.value(depth)?;
        match &node.value {
            Value::Object(value) if value.len() == 1 => value
                .get("Local")
                .and_then(Value::as_u64)
                .and_then(|n| u32::try_from(n).ok()),
            Value::Number(value) => value.as_u64().and_then(|n| u32::try_from(n).ok()),
            _ => None,
        }
        .ok_or_else(|| location.invalid("expected local fact fN or unsigned register ID"))
    }
    fn ref_node(&mut self, name: &str, id: u32) -> Result<Node, String> {
        let mut values = Map::new();
        values.insert(name.into(), Value::Number(Number::from(id)));
        self.node(Value::Object(values), Tag::Reference)
    }
    fn reference(&mut self, name: &str, depth: usize) -> Result<Node, String> {
        self.expect('(')?;
        let id = self.unsigned(depth + 1)?;
        self.expect(')')?;
        self.ref_node(reference_builtin(name).unwrap(), id)
    }
    fn ref_argument(&mut self, depth: usize) -> Result<Node, String> {
        let location = self.token.location;
        let node = self.value(depth)?;
        serde_json::from_value::<crate::proof::Ref>(node.value.clone())
            .map_err(|_| location.invalid("expected a proof reference"))?;
        Ok(node)
    }
    fn lin(&mut self, depth: usize) -> Result<Node, String> {
        self.expect('.')?;
        let location = self.token.location;
        let kind = match self.ident()?.as_str() {
            "le" => "Le",
            "eq" => "Eq",
            "int" => "Int",
            _ => return Err(location.invalid("expected lin.le, lin.eq or lin.int")),
        };
        self.expect('(')?;
        let id = self.register(depth + 1)?;
        self.expect(',')?;
        let expression = self.arithmetic(Context::References, depth + 1)?;
        self.expect(')')?;
        let nodes = 6 + expression
            .terms
            .iter()
            .map(|(atom, _)| {
                let Atom::Reference(reference) = atom else {
                    unreachable!()
                };
                shape(reference).0 + 2
            })
            .sum::<usize>();
        self.charge(nodes)?;
        let mut payload = Map::new();
        payload.insert("id".into(), Value::from(id));
        payload.insert("kind".into(), Value::String(kind.into()));
        payload.insert(
            "constant".into(),
            Value::String(expression.constant.to_string()),
        );
        payload.insert("terms".into(), Value::Array(Vec::new()));
        let mut variant = Map::new();
        variant.insert("Lin".into(), Value::Object(payload));
        self.charge_bytes(shape(&Value::Object(variant.clone())).2)?;
        let mut terms = Vec::new();
        for (atom, coefficient) in expression.terms {
            let Atom::Reference(reference) = atom else {
                unreachable!()
            };
            let text = coefficient.to_string();
            self.charge_bytes(
                shape(&reference).2 + string_bytes(&text) + 3 + usize::from(!terms.is_empty()),
            )?;
            terms
                .try_reserve(1)
                .map_err(|_| self.token.location.resource("linear output allocation"))?;
            terms.push(Value::Array(vec![reference, Value::String(text)]));
        }
        variant
            .get_mut("Lin")
            .unwrap()
            .as_object_mut()
            .unwrap()
            .insert("terms".into(), Value::Array(terms));
        Ok(uncharged_node(Value::Object(variant), Tag::Plain))
    }
    fn round(&mut self, depth: usize) -> Result<Node, String> {
        self.expect('(')?;
        let id = self.register(depth + 1)?;
        self.expect(',')?;
        let le = self.ref_argument(depth + 1)?;
        self.expect(',')?;
        let integer = self.ref_argument(depth + 1)?;
        self.expect(')')?;
        let mut payload = Map::new();
        payload.insert("id".into(), Value::from(id));
        payload.insert("le".into(), le.value);
        payload.insert("integer".into(), integer.value);
        let mut variant = Map::new();
        variant.insert("Round".into(), Value::Object(payload));
        self.node(Value::Object(variant), Tag::Plain)
    }
    fn drop_step(&mut self, depth: usize) -> Result<Node, String> {
        self.expect('(')?;
        let mut ids = Vec::new();
        while self.token.kind != TokenKind::Punct(')') {
            ids.try_reserve(1)
                .map_err(|_| self.token.location.resource("drop allocation"))?;
            ids.push(Value::from(self.register(depth + 1)?));
            if self.take(',')? {
                continue;
            }
            if self.token.kind != TokenKind::Punct(')') {
                return Err(self.token.location.invalid("expected ',' or ')'"));
            }
        }
        self.expect(')')?;
        let mut payload = Map::new();
        payload.insert("ids".into(), Value::Array(ids));
        let mut variant = Map::new();
        variant.insert("Drop".into(), Value::Object(payload));
        self.node(Value::Object(variant), Tag::Plain)
    }
    fn expand(&mut self, name: &str, depth: usize) -> Result<Node, String> {
        self.expect('(')?;
        let first = self.unsigned(depth + 1)?;
        self.expect(',')?;
        let (count, template, second) = if name == "repeat" {
            (first, Some(self.value(depth + 1)?), 0)
        } else if name == "pairs" {
            let second = self.unsigned(depth + 1)?;
            self.expect(',')?;
            (self.unsigned(depth + 1)?, None, second)
        } else {
            (self.unsigned(depth + 1)?, None, 0)
        };
        self.expect(')')?;
        if name != "repeat" && count > 0 {
            first
                .checked_add(count - 1)
                .ok_or_else(|| self.token.location.invalid("expanded ID out of range"))?;
            if name == "pairs" {
                second.checked_add(count - 1).ok_or_else(|| {
                    self.token
                        .location
                        .invalid("expanded output ID out of range")
                })?;
            }
        }
        let item_nodes = match name {
            "repeat" => template.as_ref().unwrap().nodes,
            "identity" => 6,
            "pairs" => 3,
            _ => 1,
        };
        let total = item_nodes
            .checked_mul(count as usize)
            .and_then(|n| n.checked_add(1))
            .ok_or_else(|| self.token.location.resource("expanded node budget"))?;
        self.charge(total)?;
        let item_depth = match name {
            "repeat" => template.as_ref().unwrap().depth,
            "identity" => 4,
            "pairs" => 2,
            _ => 1,
        };
        if count > 0 && depth.saturating_add(item_depth) > MAX_SOURCE_DEPTH {
            return Err(self.token.location.resource("expanded nesting depth"));
        }
        let mut bytes = 2 + (count as usize).saturating_sub(1);
        if name == "repeat" {
            bytes = template
                .as_ref()
                .unwrap()
                .bytes
                .checked_mul(count as usize)
                .and_then(|n| n.checked_add(bytes))
                .ok_or_else(|| {
                    self.token
                        .location
                        .resource("expanded byte allocation budget")
                })?;
        } else {
            for offset in 0..count {
                bytes = bytes
                    .checked_add(match name {
                        "identity" => identity_bytes(first + offset),
                        "pairs" => {
                            3 + decimal_digits(first + offset) + decimal_digits(second + offset)
                        }
                        _ => decimal_digits(first + offset),
                    })
                    .ok_or_else(|| {
                        self.token
                            .location
                            .resource("expanded byte allocation budget")
                    })?;
                if bytes > MAX_SOURCE_BYTES {
                    return Err(self
                        .token
                        .location
                        .resource("expanded byte allocation budget"));
                }
            }
        }
        self.charge_bytes(bytes)?;
        let mut values = Vec::new();
        values
            .try_reserve_exact(count as usize)
            .map_err(|_| self.token.location.resource("expansion allocation"))?;
        for offset in 0..count {
            let value = match name {
                "repeat" => template.as_ref().unwrap().value.clone(),
                "identity" => identity_value(first + offset),
                "pairs" => Value::Array(vec![
                    Value::from(first + offset),
                    Value::from(second + offset),
                ]),
                _ => Value::from(first + offset),
            };
            values.push(value);
        }
        Ok(Node {
            value: Value::Array(values),
            nodes: total,
            depth: if count == 0 { 1 } else { item_depth + 1 },
            bytes,
            tag: Tag::Plain,
        })
    }
    fn expr_node(&mut self, expression: Linear) -> Result<Node, String> {
        let location = self.token.location;
        let mut combined = BTreeMap::<u32, Q>::new();
        for (atom, coefficient) in expression.terms {
            let Atom::Coordinate(id) = atom else {
                unreachable!()
            };
            let value = combined.entry(id).or_insert_with(Q::zero);
            *value += coefficient;
            check_q(value).map_err(|e| location.wrap(e))?;
        }
        self.charge(3 + 3 * combined.values().filter(|q| !q.is_zero()).count())?;
        let mut payload = Map::new();
        payload.insert(
            "constant".into(),
            Value::String(expression.constant.to_string()),
        );
        payload.insert("terms".into(), Value::Array(Vec::new()));
        self.charge_bytes(shape(&Value::Object(payload.clone())).2)?;
        let mut terms = Vec::new();
        for (id, q) in combined.into_iter().filter(|(_, q)| !q.is_zero()) {
            let text = q.to_string();
            self.charge_bytes(
                decimal_digits(id) + string_bytes(&text) + 3 + usize::from(!terms.is_empty()),
            )?;
            terms
                .try_reserve(1)
                .map_err(|_| self.token.location.resource("expression output allocation"))?;
            terms.push(Value::Array(vec![Value::from(id), Value::String(text)]));
        }
        payload.insert("terms".into(), Value::Array(terms));
        Ok(uncharged_node(Value::Object(payload), Tag::Expression))
    }
    fn arithmetic(&mut self, context: Context, depth: usize) -> Result<Linear, String> {
        self.depth(depth)?;
        // Parentheses and unary chains use explicit stacks. Hostile source at
        // the documented depth bound must not consume the Rust call stack.
        let mut values: Vec<Linear> = Vec::new();
        let mut operators: Vec<ArithmeticOp> = Vec::new();
        let mut context = context;
        let mut current_depth = depth;
        let mut groups = 0;
        let mut expect_atom = true;
        loop {
            if expect_atom {
                let unary = match self.token.kind {
                    TokenKind::Punct('+') => Some(ArithmeticOp::Positive),
                    TokenKind::Punct('-') => Some(ArithmeticOp::Negate),
                    _ => None,
                };
                if let Some(operator) = unary {
                    self.bump()?;
                    current_depth += 1;
                    self.depth(current_depth)?;
                    operators
                        .try_reserve(1)
                        .map_err(|_| self.token.location.resource("operator allocation"))?;
                    operators.push(operator);
                    continue;
                }
                let grouping = if self.token.kind == TokenKind::Punct('(') {
                    Some((context, false))
                } else if self.ident_is("q") {
                    self.bump()?;
                    Some((Context::Scalar, false))
                } else if self.ident_is("expr") {
                    if context != Context::Coordinates {
                        return Err(self
                            .token
                            .location
                            .invalid("coordinate expression is not permitted here"));
                    }
                    self.bump()?;
                    Some((Context::Coordinates, true))
                } else {
                    None
                };
                if let Some((inner_context, canonical)) = grouping {
                    self.expect('(')?;
                    current_depth += 1;
                    self.depth(current_depth)?;
                    operators
                        .try_reserve(1)
                        .map_err(|_| self.token.location.resource("operator allocation"))?;
                    operators.push(ArithmeticOp::Open { context, canonical });
                    context = inner_context;
                    groups += 1;
                    continue;
                }
                let atom = self.arithmetic_atom(context, current_depth)?;
                values
                    .try_reserve(1)
                    .map_err(|_| self.token.location.resource("arithmetic value allocation"))?;
                values.push(atom);
                while operators.last().is_some_and(ArithmeticOp::unary) {
                    let operator = operators.pop().unwrap();
                    self.apply_operator(operator, &mut values)?;
                    current_depth -= 1;
                }
                expect_atom = false;
                continue;
            }
            if self.token.kind == TokenKind::Punct(')') && groups > 0 {
                while !matches!(operators.last(), Some(ArithmeticOp::Open { .. })) {
                    let operator = operators.pop().ok_or_else(|| {
                        self.token
                            .location
                            .invalid("unbalanced arithmetic parentheses")
                    })?;
                    self.apply_operator(operator, &mut values)?;
                }
                let ArithmeticOp::Open {
                    context: outer_context,
                    canonical,
                } = operators.pop().unwrap()
                else {
                    unreachable!()
                };
                if canonical {
                    let expression = values.last_mut().unwrap();
                    expression.canonicalize(self.token.location)?;
                }
                context = outer_context;
                groups -= 1;
                current_depth -= 1;
                self.bump()?;
                while operators.last().is_some_and(ArithmeticOp::unary) {
                    let operator = operators.pop().unwrap();
                    self.apply_operator(operator, &mut values)?;
                    current_depth -= 1;
                }
                continue;
            }
            let operator = match self.token.kind {
                TokenKind::Punct('+') => Some(ArithmeticOp::Add),
                TokenKind::Punct('-') => Some(ArithmeticOp::Subtract),
                TokenKind::Punct('*') => Some(ArithmeticOp::Multiply),
                TokenKind::Punct('/') => Some(ArithmeticOp::Divide),
                _ => None,
            };
            if let Some(operator) = operator {
                while operators
                    .last()
                    .is_some_and(|top| top.precedence() >= operator.precedence())
                {
                    let top = operators.pop().unwrap();
                    self.apply_operator(top, &mut values)?;
                }
                self.bump()?;
                operators
                    .try_reserve(1)
                    .map_err(|_| self.token.location.resource("operator allocation"))?;
                operators.push(operator);
                expect_atom = true;
            } else {
                break;
            }
        }
        if groups != 0 {
            return Err(self
                .token
                .location
                .invalid("unclosed arithmetic parentheses"));
        }
        while let Some(operator) = operators.pop() {
            self.apply_operator(operator, &mut values)?;
        }
        if values.len() != 1 {
            return Err(self.token.location.invalid("malformed affine expression"));
        }
        Ok(values.pop().unwrap())
    }
    fn apply_operator(
        &mut self,
        operator: ArithmeticOp,
        values: &mut Vec<Linear>,
    ) -> Result<(), String> {
        let location = self.token.location;
        let mut right = values
            .pop()
            .ok_or_else(|| location.invalid("missing arithmetic operand"))?;
        if operator.unary() {
            if matches!(operator, ArithmeticOp::Negate) {
                right.negate();
            }
            values.push(right);
            return Ok(());
        }
        let mut left = values
            .pop()
            .ok_or_else(|| location.invalid("missing arithmetic operand"))?;
        match operator {
            ArithmeticOp::Add | ArithmeticOp::Subtract => {
                if matches!(operator, ArithmeticOp::Subtract) {
                    right.negate();
                }
                self.charge_bytes(rational_add_bound(&left.constant, &right.constant))?;
                left.constant += right.constant;
                check_q(&left.constant).map_err(|e| location.wrap(e))?;
                self.charge(right.terms.len())?;
                left.terms
                    .try_reserve(right.terms.len())
                    .map_err(|_| location.resource("arithmetic term allocation"))?;
                left.terms.extend(right.terms);
            }
            ArithmeticOp::Divide => {
                if !right.terms.is_empty() {
                    return Err(location.invalid("division by a nonconstant expression"));
                }
                if right.constant.is_zero() {
                    return Err(location.invalid("division by zero"));
                }
                self.scale_linear(&mut left, Q::one() / right.constant, location)?;
            }
            ArithmeticOp::Multiply => {
                if right.terms.is_empty() {
                    self.scale_linear(&mut left, right.constant, location)?;
                } else if left.terms.is_empty() {
                    let factor = left.constant;
                    left = right;
                    self.scale_linear(&mut left, factor, location)?;
                } else {
                    return Err(location.invalid("nonaffine multiplication"));
                }
            }
            _ => return Err(location.invalid("unbalanced arithmetic operator")),
        }
        values.push(left);
        Ok(())
    }
    fn scale_linear(
        &mut self,
        expression: &mut Linear,
        factor: Q,
        location: Location,
    ) -> Result<(), String> {
        let bytes = std::iter::once(&expression.constant)
            .chain(expression.terms.iter().map(|(_, q)| q))
            .try_fold(0usize, |bytes, q| {
                bytes.checked_add(rational_multiply_bound(q, &factor))
            })
            .ok_or_else(|| location.resource("arithmetic allocation budget"))?;
        self.charge_bytes(bytes)?;
        expression.scale(factor, location)
    }
    fn charge_rationals(&mut self, expression: &Linear) -> Result<(), String> {
        // Account for large coefficients produced from tiny exponent literals
        // before retaining them in long affine vectors.
        let bytes = std::iter::once(&expression.constant)
            .chain(expression.terms.iter().map(|(_, q)| q))
            .try_fold(0usize, |bytes, q| {
                let bits = q.numer().bits().checked_add(q.denom().bits())?;
                bytes.checked_add(usize::try_from(bits.div_ceil(8)).ok()?)
            })
            .ok_or_else(|| self.token.location.resource("arithmetic allocation budget"))?;
        self.charge_bytes(bytes)
    }
    fn arithmetic_atom(&mut self, context: Context, depth: usize) -> Result<Linear, String> {
        self.depth(depth)?;
        let location = self.token.location;
        match self.token.kind.clone() {
            TokenKind::Number(text) => {
                self.bump()?;
                let expression = Linear::constant(parse_q(&text).map_err(|e| location.wrap(e))?);
                self.charge(1)?;
                self.charge_rationals(&expression)?;
                Ok(expression)
            }
            TokenKind::Ident(_) | TokenKind::String(_) => {
                let node = self.value(depth)?;
                match node.tag {
                    Tag::Scalar(q) => Ok(Linear::constant(q)),
                    Tag::Coordinate(id) if context == Context::Coordinates => {
                        Ok(Linear::atom(Atom::Coordinate(id)))
                    }
                    Tag::Reference if context == Context::References => {
                        Ok(Linear::atom(Atom::Reference(node.value)))
                    }
                    Tag::Expression if context == Context::Coordinates => {
                        self.expression_alias(node.value, location)
                    }
                    Tag::Plain => {
                        if let Some(text) = node.value.as_str() {
                            match parse_q(text) {
                                Ok(q) => return Ok(Linear::constant(q)),
                                Err(error) if error.starts_with("RESOURCE_LIMIT") => {
                                    return Err(location.wrap(error));
                                }
                                Err(_) => {}
                            }
                        }
                        if let Some(number) = node.value.as_u64() {
                            return Ok(Linear::constant(Q::from_integer(number.into())));
                        }
                        if context == Context::References
                            && serde_json::from_value::<crate::proof::Ref>(node.value.clone())
                                .is_ok()
                        {
                            return Ok(Linear::atom(Atom::Reference(node.value)));
                        }
                        Err(location.invalid("expected scalar or permitted affine atom"))
                    }
                    _ => Err(location.invalid("affine atom is not permitted in this expression")),
                }
            }
            _ => Err(location.invalid("expected exact affine expression")),
        }
    }
    fn expression_alias(&self, value: Value, location: Location) -> Result<Linear, String> {
        let expression: crate::model::Expr =
            serde_json::from_value(value).map_err(|e| location.invalid(e))?;
        Ok(Linear {
            constant: expression.constant,
            terms: expression
                .terms
                .into_iter()
                .map(|(id, q)| (Atom::Coordinate(id), q))
                .collect(),
        })
    }
}

#[derive(Clone, Copy, PartialEq)]
enum Context {
    Scalar,
    Coordinates,
    References,
}

enum ArithmeticOp {
    Add,
    Subtract,
    Multiply,
    Divide,
    Positive,
    Negate,
    Open { context: Context, canonical: bool },
}

impl ArithmeticOp {
    fn unary(&self) -> bool {
        matches!(self, Self::Positive | Self::Negate)
    }
    fn precedence(&self) -> usize {
        match self {
            Self::Open { .. } => 0,
            Self::Add | Self::Subtract => 1,
            Self::Multiply | Self::Divide => 2,
            _ => 3,
        }
    }
}

enum Atom {
    Coordinate(u32),
    Reference(Value),
}

struct Linear {
    constant: Q,
    terms: Vec<(Atom, Q)>,
}

impl Linear {
    fn constant(constant: Q) -> Self {
        Self {
            constant,
            terms: Vec::new(),
        }
    }
    fn atom(atom: Atom) -> Self {
        Self {
            constant: Q::zero(),
            terms: vec![(atom, Q::one())],
        }
    }
    fn negate(&mut self) {
        self.constant = -self.constant.clone();
        for (_, coefficient) in &mut self.terms {
            *coefficient = -coefficient.clone();
        }
    }
    fn scale(&mut self, factor: Q, location: Location) -> Result<(), String> {
        self.constant *= &factor;
        check_q(&self.constant).map_err(|e| location.wrap(e))?;
        for (_, coefficient) in &mut self.terms {
            *coefficient *= &factor;
            check_q(coefficient).map_err(|e| location.wrap(e))?;
        }
        Ok(())
    }
    fn canonicalize(&mut self, location: Location) -> Result<(), String> {
        let mut combined = BTreeMap::<u32, Q>::new();
        for (atom, coefficient) in self.terms.drain(..) {
            let Atom::Coordinate(id) = atom else {
                return Err(location.invalid("expected coordinate expression"));
            };
            let q = combined.entry(id).or_insert_with(Q::zero);
            *q += coefficient;
            check_q(q).map_err(|e| location.wrap(e))?;
        }
        self.terms = combined
            .into_iter()
            .filter(|(_, q)| !q.is_zero())
            .map(|(id, q)| (Atom::Coordinate(id), q))
            .collect();
        Ok(())
    }
}

fn uncharged_node(value: Value, tag: Tag) -> Node {
    let (nodes, depth, bytes) = shape(&value);
    Node {
        value,
        nodes,
        depth,
        bytes,
        tag,
    }
}

fn shape(value: &Value) -> (usize, usize, usize) {
    let children: Box<dyn Iterator<Item = &Value> + '_> = match value {
        Value::Array(values) => Box::new(values.iter()),
        Value::Object(values) => Box::new(values.values()),
        Value::String(text) => return (1, 1, string_bytes(text)),
        Value::Number(number) => return (1, 1, number.to_string().len()),
        Value::Bool(value) => return (1, 1, if *value { 4 } else { 5 }),
        Value::Null => return (1, 1, 4),
    };
    let mut nodes = 1;
    let mut depth = 1;
    let mut bytes = match value {
        Value::Array(values) => 2 + values.len().saturating_sub(1),
        Value::Object(values) => {
            2 + values.len().saturating_sub(1)
                + values
                    .keys()
                    .map(|key| string_bytes(key) + 1)
                    .sum::<usize>()
        }
        _ => unreachable!(),
    };
    for child in children {
        let (child_nodes, child_depth, child_bytes) = shape(child);
        nodes += child_nodes;
        depth = depth.max(child_depth + 1);
        bytes += child_bytes;
    }
    (nodes, depth, bytes)
}

fn string_bytes(text: &str) -> usize {
    2 + text
        .bytes()
        .map(|byte| match byte {
            b'"' | b'\\' | b'\x08' | b'\t' | b'\n' | b'\x0c' | b'\r' => 2,
            0..=31 => 6,
            _ => 1,
        })
        .sum::<usize>()
}

fn decimal_digits(value: u32) -> usize {
    if value == 0 {
        1
    } else {
        value.ilog10() as usize + 1
    }
}
fn identity_bytes(id: u32) -> usize {
    "{\"constant\":\"0\",\"terms\":[[".len() + decimal_digits(id) + ",\"1\"]]}".len()
}

fn rational_multiply_bound(left: &Q, right: &Q) -> usize {
    ((left.numer().bits() + right.numer().bits()).div_ceil(8)
        + (left.denom().bits() + right.denom().bits()).div_ceil(8)) as usize
}

fn rational_add_bound(left: &Q, right: &Q) -> usize {
    let numerator = (left.numer().bits() + right.denom().bits())
        .max(right.numer().bits() + left.denom().bits())
        + 1;
    (numerator.div_ceil(8) + (left.denom().bits() + right.denom().bits()).div_ceil(8)) as usize
}

fn identity_value(id: u32) -> Value {
    let mut fields = Map::new();
    fields.insert("constant".into(), Value::String("0".into()));
    fields.insert(
        "terms".into(),
        Value::Array(vec![Value::Array(vec![
            Value::from(id),
            Value::String("1".into()),
        ])]),
    );
    Value::Object(fields)
}

fn coordinate_name(name: &str) -> Option<&str> {
    numbered_name(name, 'x')
}
fn fact_name(name: &str) -> Option<&str> {
    numbered_name(name, 'f')
}
fn numbered_name(name: &str, prefix: char) -> Option<&str> {
    let rest = name.strip_prefix(prefix)?;
    (!rest.is_empty() && rest.bytes().all(|c| c.is_ascii_digit())).then_some(rest)
}
fn reference_builtin(name: &str) -> Option<&'static str> {
    Some(match name {
        "lower" => "VarLower",
        "upper" => "VarUpper",
        "integer" => "VarInt",
        "row_lower" => "RowLower",
        "row_upper" => "RowUpper",
        "row_eq" => "RowEq",
        "assumption" => "Assumption",
        "local" => "Local",
        _ => return None,
    })
}
fn expansion(name: &str) -> bool {
    matches!(name, "repeat" | "identity" | "range" | "pairs")
}
fn variant(name: &str) -> bool {
    matches!(
        name,
        "None"
            | "Equal"
            | "NonIncreasing"
            | "Le"
            | "Eq"
            | "Int"
            | "Exact"
            | "VarLower"
            | "VarUpper"
            | "VarInt"
            | "RowLower"
            | "RowUpper"
            | "RowEq"
            | "Local"
            | "Assumption"
            | "Lin"
            | "Round"
            | "Drop"
            | "EqPair"
            | "Cases"
            | "Plotkin"
            | "Return"
            | "Split"
            | "Absurd"
            | "Witness"
            | "FlowLift"
            | "IntervalLift"
            | "MenuLift"
            | "SignedLift"
            | "SubflowLift"
            | "ImproveReturn"
            | "PositiveRefutation"
            | "Constant"
            | "Predicate"
            | "Feasible"
            | "Strictness"
            | "FiberStrictness"
            | "ImageExclusion"
    )
}
fn reserved(name: &str) -> bool {
    matches!(
        name,
        "let"
            | "models"
            | "certificate"
            | "true"
            | "false"
            | "null"
            | "q"
            | "expr"
            | "exact"
            | "lin"
            | "round"
            | "drop"
    ) || reference_builtin(name).is_some()
        || expansion(name)
        || variant(name)
        || coordinate_name(name).is_some()
        || fact_name(name).is_some()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn aliases_expressions_and_steps_lower_exactly() {
        let value = parse_body(
            r#"
            // A coordinate alias and a fact alias stay explicit.
            let demand = x2;
            let bound = row_upper(1);
            certificate {
                claims: [],
                blocks: [{steps: [
                    lin.eq(f4, -bound + 2*lower(x0) + 1/3),
                    round(f5, f4, integer(demand)), drop(f4, f5),
                ], end: Return {
                    map: [expr(1 - 2*demand + x0 + demand), identity(3, 2)],
                    checks: [repeat(2, exact)],
                }}],
            }
        "#,
        )
        .unwrap();
        assert_eq!(
            value["blocks"][0]["steps"][0]["Lin"]["terms"],
            serde_json::json!([[{"RowUpper":1},"-1"],[{"VarLower":0},"2"]])
        );
        assert_eq!(
            value["blocks"][0]["end"]["Return"]["map"][0],
            serde_json::json!({"constant":"1","terms":[[0,"1"],[2,"-1"]]})
        );
        assert_eq!(
            value["blocks"][0]["end"]["Return"]["map"]
                .as_array()
                .unwrap()
                .len(),
            3
        );
        assert_eq!(
            value["blocks"][0]["end"]["Return"]["checks"],
            serde_json::json!(["Exact", "Exact"])
        );
    }

    #[test]
    fn source_rejects_ambiguous_or_invalid_inputs() {
        for source in [
            "let name = x0; let name = x1; certificate {}",
            "let x0 = 2; certificate {}",
            "let name = missing; certificate {}",
            "certificate {a: 1, a: 2}",
            "certificate {a: expr(x0*x1)}",
            "certificate {a: expr(1/x0)}",
            "certificate {a: lower(-1)}",
            "certificate {a: lower(4294967296)}",
            "certificate {a: x4294967296}",
            "certificate {a: q(1/0)}",
            "certificate {a: 0.5}",
            "certificate {a: round(f0, 1, exact)}",
            "certificate {} /* unterminated",
            "certificate {a: [pairs(4294967295, 0, 2)]}",
        ] {
            assert!(
                parse_body(source)
                    .unwrap_err()
                    .starts_with("INVALID RPA source"),
                "{source}"
            );
        }
    }

    #[test]
    fn expansions_are_bounded_before_allocating() {
        for source in [
            "certificate {a: [repeat(16000001, exact)]}",
            "certificate {a: [identity(0, 3000000)]}",
        ] {
            assert!(
                parse_body(source)
                    .unwrap_err()
                    .starts_with("RESOURCE_LIMIT")
            );
        }
        let source = format!("certificate {{a: {}0{}}}", "[".repeat(130), "]".repeat(130));
        assert!(
            parse_body(&source)
                .unwrap_err()
                .starts_with("RESOURCE_LIMIT")
        );
        let large_string = "x".repeat(65_536);
        let source =
            format!("let text = \"{large_string}\"; certificate {{a:[repeat(100000,text)]}}");
        assert!(
            parse_body(&source)
                .unwrap_err()
                .starts_with("RESOURCE_LIMIT")
        );
    }

    #[test]
    fn arithmetic_parentheses_are_depth_bounded() {
        let source = format!(
            "certificate {{a:q({}1{})}}",
            "(".repeat(140),
            ")".repeat(140)
        );
        assert!(
            parse_body(&source)
                .unwrap_err()
                .starts_with("RESOURCE_LIMIT")
        );
        let source = format!("certificate {{a:q({}1)}}", "-".repeat(140));
        assert!(
            parse_body(&source)
                .unwrap_err()
                .starts_with("RESOURCE_LIMIT")
        );
        let source = format!("certificate {{a:{}1{}}}", "q(".repeat(140), ")".repeat(140));
        assert!(
            parse_body(&source)
                .unwrap_err()
                .starts_with("RESOURCE_LIMIT")
        );
    }

    #[test]
    fn variant_wrappers_are_depth_bounded() {
        let source = format!(
            "certificate {{a:{}exact{}}}",
            "Witness(".repeat(140),
            ")".repeat(140)
        );
        assert!(
            parse_body(&source)
                .unwrap_err()
                .starts_with("RESOURCE_LIMIT")
        );
    }

    #[test]
    fn constructor_recursion_is_depth_bounded() {
        let source = format!(
            "certificate {{a:{}null{}}}",
            "repeat(0,".repeat(140),
            ")".repeat(140)
        );
        assert!(
            parse_body(&source)
                .unwrap_err()
                .starts_with("RESOURCE_LIMIT")
        );
        let source = format!(
            "certificate {{a:{}0{}}}",
            "lower(".repeat(140),
            ")".repeat(140)
        );
        assert!(
            parse_body(&source)
                .unwrap_err()
                .starts_with("RESOURCE_LIMIT")
        );
    }

    #[test]
    fn scaling_is_preflighted_before_coefficients_are_mutated() {
        let mut lexer = Lexer::new("");
        let token = lexer.next().unwrap();
        let mut parser = Parser {
            lexer,
            token,
            aliases: HashMap::new(),
            used_nodes: 0,
            used_bytes: MAX_SOURCE_BYTES - 100,
        };
        let mut expression = Linear {
            constant: Q::zero(),
            terms: (0..20)
                .map(|_| (Atom::Reference(Value::String("Exact".into())), Q::one()))
                .collect(),
        };
        let error = parser
            .scale_linear(
                &mut expression,
                parse_q("1e4000").unwrap(),
                Location { line: 2, column: 1 },
            )
            .unwrap_err();
        assert!(error.starts_with("RESOURCE_LIMIT"));
        assert!(expression.terms.iter().all(|(_, q)| q.is_one()));
    }

    #[test]
    fn arithmetic_precedence_and_nested_contexts_are_exact() {
        let value = parse_body("certificate {a:q(1+2*3), b:q((1+2)*3), c:q(8/4/2), d:q(1--2), e:q(-2*-3), f:expr(q(1/3)*(x1-x0)), g:expr(expr(x0-x0)*x1)}").unwrap();
        assert_eq!(value["a"], "7");
        assert_eq!(value["b"], "9");
        assert_eq!(value["c"], "1");
        assert_eq!(value["d"], "3");
        assert_eq!(value["e"], "6");
        assert_eq!(
            value["f"],
            serde_json::json!({"constant":"0","terms":[[0,"-1/3"],[1,"1/3"]]})
        );
        assert_eq!(value["g"], serde_json::json!({"constant":"0","terms":[]}));
    }

    #[test]
    fn generic_variants_and_scalars_cover_current_schema() {
        let value = parse_body("certificate {a: Witness(f0), b: Absurd {fact: exact}, c: Constant(q(2/6)), d: Predicate(q(0.125)), e: [(x0,x1), pairs(2,4,2)], f: [range(0,3)], g: q(2D+3)}").unwrap();
        assert_eq!(value["a"], serde_json::json!({"Witness":{"Local":0}}));
        assert_eq!(value["c"], serde_json::json!({"Constant":"1/3"}));
        assert_eq!(value["d"], serde_json::json!({"Predicate":"1/8"}));
        assert_eq!(value["e"], serde_json::json!([[0, 1], [2, 4], [3, 5]]));
        assert_eq!(value["g"], "2000");
    }
}
