//! Fixed Windows helper request and result vocabulary; no command interpretation.
use super::{ActionError, ProcessActionOutcome, ProcessIdentity, ProcessSignal};
use std::ffi::OsString;

pub(super) const HELPER_MODE: &str = "--system-pulse-windows-process-action";

#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) struct Request {
    pub target: ProcessIdentity,
    pub signal: ProcessSignal,
    pub caller: ProcessIdentity,
}

impl Request {
    pub fn parse(arguments: &[OsString]) -> Result<Self, Failure> {
        if arguments.len() != 6 || arguments[0] != HELPER_MODE {
            return Err(Failure::InvalidRequest);
        }
        let parse = |pid: &OsString, ticks: &OsString, signal: &OsString| {
            super::authentication::parse_request(&[
                "--system-pulse-process-action".into(),
                pid.clone(),
                ticks.clone(),
                signal.clone(),
            ])
            .map_err(|_| Failure::InvalidRequest)
        };
        let (target, signal) = parse(&arguments[1], &arguments[2], &arguments[3])?;
        let (caller, _) = parse(&arguments[4], &arguments[5], &OsString::from("kill"))?;
        if target.pid == caller.pid {
            return Err(Failure::Protected);
        }
        Ok(Self {
            target,
            signal,
            caller,
        })
    }

    pub fn parameters(&self) -> String {
        // Every variable field is formatted from an integer or a closed enum.
        // The executable path is a separate ShellExecuteExW parameter.
        format!(
            "{HELPER_MODE} {} {} {} {} {}",
            self.target.pid,
            self.target.start_time_ticks,
            match self.signal {
                ProcessSignal::Terminate => "terminate",
                ProcessSignal::Kill => "kill",
            },
            self.caller.pid,
            self.caller.start_time_ticks
        )
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) enum Failure {
    PermissionDenied,
    Protected,
    IdentityChanged,
    TargetExited,
    GracefulUnavailable,
    CloseRefused,
    Cancelled,
    InvalidRequest,
    UnknownOutcome,
    OperatingSystem { operation: &'static str, code: u32 },
}

impl std::fmt::Display for Failure {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            Self::PermissionDenied => "Windows denied the requested process action.",
            Self::Protected => "This process is protected from task actions.",
            Self::IdentityChanged => "The selected process identity changed. Select the process again.",
            Self::TargetExited => "The selected process has already exited.",
            Self::GracefulUnavailable => "Graceful close is unavailable for this process. You can separately confirm Force quit if termination is intended.",
            Self::CloseRefused => "The application did not close. It may need a response or have declined the request. Check its window before choosing Force quit.",
            Self::Cancelled => "Windows authorization was cancelled. No helper action was started.",
            Self::InvalidRequest => "The Windows process-action request was invalid.",
            Self::UnknownOutcome => "The process-action helper did not confirm an outcome. Check the process list before trying again.",
            Self::OperatingSystem { operation, code } => return write!(f,
                "{operation} failed (Windows error {code}). Check the process list before trying again."),
        })
    }
}

impl From<Failure> for ActionError {
    fn from(failure: Failure) -> Self {
        match failure {
            Failure::PermissionDenied => Self::PermissionDenied,
            _ => Self::Failed(failure.to_string()),
        }
    }
}

pub(super) fn encode_result(result: Result<ProcessActionOutcome, Failure>) -> i32 {
    match result {
        Ok(ProcessActionOutcome::ExitObserved) => 20,
        Ok(ProcessActionOutcome::CloseRequested) => 21,
        Ok(ProcessActionOutcome::TerminationPending) => 22,
        Err(Failure::PermissionDenied) => 23,
        Err(Failure::Protected) => 24,
        Err(Failure::IdentityChanged) => 25,
        Err(Failure::TargetExited) => 26,
        Err(Failure::GracefulUnavailable) => 27,
        Err(Failure::CloseRefused) => 28,
        Err(Failure::InvalidRequest) => 29,
        Err(Failure::Cancelled) => 30,
        _ => 31,
    }
}

pub(super) fn decode_result(code: u32) -> Result<ProcessActionOutcome, Failure> {
    match code {
        20 => Ok(ProcessActionOutcome::ExitObserved),
        21 => Ok(ProcessActionOutcome::CloseRequested),
        22 => Ok(ProcessActionOutcome::TerminationPending),
        23 => Err(Failure::PermissionDenied),
        24 => Err(Failure::Protected),
        25 => Err(Failure::IdentityChanged),
        26 => Err(Failure::TargetExited),
        27 => Err(Failure::GracefulUnavailable),
        28 => Err(Failure::CloseRefused),
        29 => Err(Failure::InvalidRequest),
        30 => Err(Failure::Cancelled),
        _ => Err(Failure::UnknownOutcome),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request() -> Request {
        Request {
            target: ProcessIdentity {
                pid: 4242,
                start_time_ticks: 134_335_279_792_573_971,
            },
            caller: ProcessIdentity {
                pid: 4244,
                start_time_ticks: 134_335_279_692_573_123,
            },
            signal: ProcessSignal::Kill,
        }
    }

    #[test]
    fn full_filetime_and_caller_identity_round_trip_without_precision_loss() {
        for signal in [ProcessSignal::Terminate, ProcessSignal::Kill] {
            let request = Request {
                signal,
                ..request()
            };
            let args = request
                .parameters()
                .split(' ')
                .map(OsString::from)
                .collect::<Vec<_>>();
            assert_eq!(Request::parse(&args), Ok(request));
        }
    }

    #[test]
    fn malformed_or_self_targeting_requests_are_rejected() {
        let args = request()
            .parameters()
            .split(' ')
            .map(OsString::from)
            .collect::<Vec<_>>();
        for (index, value) in [
            (0, "--unrelated"),
            (1, "0"),
            (1, "4294967296"),
            (2, "0"),
            (2, "18446744073709551616"),
            (3, "kill;whoami"),
            (4, "4242"),
            (4, "-1"),
            (5, "0"),
            (5, "1 2"),
        ] {
            let mut invalid = args.clone();
            invalid[index] = value.into();
            assert!(
                Request::parse(&invalid).is_err(),
                "accepted {index}={value}"
            );
        }
        assert!(Request::parse(&args[..5]).is_err());
        let mut extra = args;
        extra.push("extra".into());
        assert!(Request::parse(&extra).is_err());
    }

    #[test]
    fn unknown_and_legacy_exit_codes_never_claim_success_or_no_change() {
        for code in [0, 1, 11, 12, 13, 259, u32::MAX] {
            assert_eq!(decode_result(code), Err(Failure::UnknownOutcome));
        }
        assert!(
            Failure::UnknownOutcome
                .to_string()
                .contains("Check the process list")
        );
        for outcome in [
            ProcessActionOutcome::ExitObserved,
            ProcessActionOutcome::CloseRequested,
            ProcessActionOutcome::TerminationPending,
        ] {
            assert_eq!(
                decode_result(encode_result(Ok(outcome)) as u32),
                Ok(outcome)
            );
        }
        assert_eq!(
            decode_result(encode_result(Err(Failure::OperatingSystem {
                operation: "Wait for helper",
                code: 6
            })) as u32),
            Err(Failure::UnknownOutcome)
        );
    }
}
