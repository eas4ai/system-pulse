use super::*;

pub(super) fn read_test_temperature(server: &OwnedHandle, expected_pid: u32) -> Result<f64> {
    let deadline = Instant::now() + Duration::from_secs(10);
    let mut connected = false;
    while Instant::now() < deadline {
        if !connected {
            match unsafe { ConnectNamedPipe(raw(server), None) } {
                Ok(()) => connected = true,
                Err(error) if code(&error) == ERROR_PIPE_CONNECTED.0 => connected = true,
                Err(error) if code(&error) == ERROR_PIPE_LISTENING.0 => {}
                Err(error) => return Err(format!("test connect: {error}")),
            }
            if connected {
                let mut pid = 0;
                unsafe { GetNamedPipeClientProcessId(raw(server), &mut pid) }
                    .map_err(|error| format!("test client identity: {error}"))?;
                if pid != expected_pid {
                    return Err("test pipe client differs from retained child".into());
                }
                eprintln!("real helper connected and PID authenticated");
            }
        }
        if connected {
            let mut bytes = [0u8; 64];
            let mut count = 0;
            match unsafe { ReadFile(raw(server), Some(&mut bytes), Some(&mut count), None) } {
                Ok(()) if count != 0 => {
                    eprintln!("real helper frame bytes={count}, raw={bytes:02x?}");
                    return Frame::decode(&bytes[..count as usize], 0)?.temperature();
                }
                Ok(()) => {}
                Err(error) if code(&error) == ERROR_NO_DATA.0 => {}
                Err(error) => return Err(format!("test read: {error}")),
            }
        }
        std::thread::sleep(POLL);
    }
    Err("real helper test timed out".into())
}

pub(super) fn write_terminal_test_frame(
    request: &Request,
    backend: Backend,
    error: Option<u64>,
) -> Result<()> {
    let name = pipe_name(request);
    let pipe = own(unsafe {
        CreateFileW(
            PCWSTR(name.as_ptr()),
            (FILE_WRITE_DATA | FILE_WRITE_ATTRIBUTES).0,
            FILE_SHARE_NONE,
            None,
            OPEN_EXISTING,
            FILE_FLAGS_AND_ATTRIBUTES(0),
            None,
        )
    }
    .map_err(|reason| format!("open terminal test pipe: {reason}"))?);
    unsafe { SetNamedPipeHandleState(raw(&pipe), Some(&PIPE_NOWAIT), None, None) }
        .map_err(|reason| format!("set terminal test pipe mode: {reason}"))?;
    if let Some(error) = error {
        let frequency = frequency()?;
        let before = counter()?;
        let after = counter()?;
        let bytes = Frame {
            backend,
            sequence: 1,
            target: 0,
            status: 0,
            before,
            after,
            frequency,
            error,
        }
        .encode();
        let mut written = 0;
        unsafe { WriteFile(raw(&pipe), Some(&bytes), Some(&mut written), None) }
            .map_err(|reason| format!("write terminal test frame: {reason}"))?;
        if written != 64 {
            return Err("terminal test frame was not written in full".into());
        }
    }
    Ok(())
}
