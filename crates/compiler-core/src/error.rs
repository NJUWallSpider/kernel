use std::fmt;

#[derive(Clone, Debug)]
pub enum Error {
    Coordinate(String),
    Scope(String),
    Mapping(String),
    Derivation(String),
    Unproved(String),
    Resource(String),
    Artifact(String),
    Invalid(String),
}
impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let (Self::Coordinate(s)
        | Self::Scope(s)
        | Self::Mapping(s)
        | Self::Derivation(s)
        | Self::Unproved(s)
        | Self::Resource(s)
        | Self::Artifact(s)
        | Self::Invalid(s)) = self;
        f.write_str(s)
    }
}
impl std::error::Error for Error {}
impl From<String> for Error {
    fn from(s: String) -> Self {
        if s.starts_with("RESOURCE_LIMIT") {
            Self::Resource(
                s.trim_start_matches("RESOURCE_LIMIT")
                    .trim_start_matches(':')
                    .trim()
                    .into(),
            )
        } else {
            Self::Invalid(s.strip_prefix("INVALID ").unwrap_or(&s).into())
        }
    }
}
