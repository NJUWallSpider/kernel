//! Independent regression tests for retained model readers and constructive lemmas.
#[path="../tests/model_export.rs"]
mod test_model_export;
#[path="../tests/lp.rs"]
mod test_lp;
#[path="../tests/menu_builder.rs"]
mod test_menu_builder;
#[path="../tests/interval_builder.rs"]
mod test_interval_builder;
#[path="../tests/flow_builder.rs"]
mod test_flow_builder;
#[path="../tests/signed_builder.rs"]
mod test_signed_builder;
#[path="../tests/subflow_builder.rs"]
mod test_subflow_builder;
#[path="../tests/oracle.rs"]
mod test_oracle;
#[path="../tests/semantics.rs"]
mod test_semantics;

#[path="../tests/adversarial_review.rs"]
mod test_adversarial;
#[path="../tests/plotkin.rs"]
mod test_plotkin;
