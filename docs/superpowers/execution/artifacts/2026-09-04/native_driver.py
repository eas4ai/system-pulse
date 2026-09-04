"""Isolated native interaction driver. Commands arrive as newline-delimited JSON."""
import hashlib, json, os, pathlib, subprocess, sys, time
import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib
from PIL import ImageGrab
from Xlib import X, XK, display, protocol
from Xlib.ext import xtest

binary = pathlib.Path(sys.argv[1])
output = pathlib.Path(sys.argv[2]); output.mkdir(parents=True, exist_ok=True)
state = output / "state"; state.mkdir(exist_ok=True)
log = open(output / "application.log", "a")
os.environ.pop("AT_SPI_BUS_ADDRESS", None)
a11y = subprocess.Popen(["/usr/libexec/at-spi-bus-launcher", "--launch-immediately", "--a11y=1", "--screen-reader=1"], env=dict(os.environ, GSETTINGS_BACKEND="memory"), stdout=log, stderr=log)
time.sleep(0.3)
app = subprocess.Popen([str(binary)], env=dict(os.environ, SYSTEM_PULSE_STATE_DIR=str(state), RUST_BACKTRACE="1"), stdout=log, stderr=log)
d = display.Display()
state_events = []

def state_event(event, *_):
    try:
        item={"type":event.type,"name":event.source.get_name(),"value":event.detail1}
        state_events.append(item)
        with (output / "state-events.jsonl").open("a") as f: f.write(json.dumps(item)+"\n")
    except Exception as e:
        state_events.append({"error":str(e)})

def spin(seconds):
    deadline = time.monotonic() + seconds
    context = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while context.pending(): context.iteration(False)
        time.sleep(0.025)

def nodes(node=None, depth=0):
    if node is None: node = Atspi.get_desktop(0)
    yield node
    if depth < 20:
        for i in range(min(node.get_child_count(), 1000)):
            child = node.get_child_at_index(i)
            if child is not None: yield from nodes(child, depth+1)

def describe(node, recursive=False, depth=0):
    result = {"role": node.get_role_name(), "name": node.get_name(), "states": [x.value_nick for x in node.get_state_set().get_states()]}
    try:
        b = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        result["bounds"] = [b.x, b.y, b.width, b.height]
    except Exception: pass
    try:
        a = node.get_action_iface()
        result["actions"] = [a.get_action_name(i) for i in range(a.get_n_actions())]
    except Exception: pass
    if recursive and depth < 16:
        result["children"] = [describe(node.get_child_at_index(i), True, depth+1) for i in range(min(node.get_child_count(), 1000))]
    return result

def selected(cmd):
    matches = [n for n in nodes() if n.get_name() == cmd["name"] and ("role" not in cmd or n.get_role_name() == cmd["role"])]
    if len(matches) != 1: raise ValueError(f"Expected one {cmd['name']!r}, found {len(matches)}")
    return matches[0]

def move(x, y):
    xtest.fake_input(d, X.MotionNotify, x=int(x), y=int(y)); d.sync()

def button(number, pressed):
    xtest.fake_input(d, X.ButtonPress if pressed else X.ButtonRelease, number); d.sync()

def windows():
    root = d.screen().root
    return [w for w in root.query_tree().children if w.get_attributes().map_state == X.IsViewable and w.get_geometry().width > 100]

def command(c):
    op = c["op"]
    if op == "events":
        return state_events
    if op == "state":
        return json.loads((state / c.get("file", "workspace.json")).read_text())
    if op == "windows":
        return [{"id": w.id, "name": w.get_wm_name(), "width": w.get_geometry().width, "height": w.get_geometry().height} for w in windows()]
    if op == "tree":
        result = describe(Atspi.get_desktop(0), True)
        (output / c.get("file", "accessibility.json")).write_text(json.dumps(result, indent=2))
        if c.get("summary"): return {"file":str(output / c.get("file", "accessibility.json"))}
        return result
    if op == "query":
        return [describe(n) for n in nodes() if c.get("contains", "").lower() in n.get_name().lower() and ("role" not in c or n.get_role_name() == c["role"])]
    if op == "action":
        a = selected(c).get_action_iface()
        result = a.do_action(c.get("index", 0))
        if not result: raise RuntimeError("AT-SPI action was rejected")
    elif op == "focus":
        if not selected(c).get_component_iface().grab_focus(): raise RuntimeError("Native focus request rejected")
    elif op == "move":
        move(*c["at"])
    elif op == "click":
        if "name" in c:
            b = selected(c).get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            x, y = b.x+b.width/2, b.y+b.height/2
        else: x, y = c["at"]
        move(x,y); button(c.get("button",1),True); button(c.get("button",1),False)
    elif op == "drag":
        x,y = c["from"]; tx,ty = c["to"]
        move(x,y); button(1,True)
        for i in range(1,21):
            move(x+(tx-x)*i/20,y+(ty-y)*i/20); spin(0.025)
        button(1,False)
    elif op == "key":
        keys = [d.keysym_to_keycode(XK.string_to_keysym(k)) for k in c["keys"]]
        if not all(keys): raise ValueError("Unknown key")
        for key in keys: xtest.fake_input(d,X.KeyPress,key)
        for key in reversed(keys): xtest.fake_input(d,X.KeyRelease,key)
        d.sync()
    elif op == "wheel":
        move(*c["at"])
        for _ in range(c.get("count",1)):
            button(c.get("button",5),True); button(c.get("button",5),False); spin(0.02)
    elif op == "resize":
        ws = windows()
        if len(ws)!=1: raise ValueError(f"Expected one app window, found {len(ws)}")
        ws[0].configure(width=c["width"],height=c["height"]); d.sync()
    elif op == "screenshot":
        path = output / c["file"]
        ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).save(path)
        return {"path": str(path)}
    elif op == "wait": spin(c.get("seconds",1))
    elif op == "quit":
        for w in windows():
            event = protocol.event.ClientMessage(window=w, client_type=d.intern_atom("WM_PROTOCOLS"),data=(32,[d.intern_atom("WM_DELETE_WINDOW"),X.CurrentTime,0,0,0]))
            w.send_event(event)
        d.sync()
        deadline=time.monotonic()+10
        while app.poll() is None and time.monotonic()<deadline: spin(0.1)
        return {"exit_code":app.poll()}
    else: raise ValueError(f"Unknown command {op}")
    spin(c.get("settle",0.5))
    return {"ok":True,"running":app.poll() is None}

try:
    Atspi.init()
    listener = Atspi.EventListener.new(state_event)
    listener.register("object:state-changed:expanded")
    listener.register("object:state-changed:expandable")
    spin(5)
    if app.poll() is not None: raise RuntimeError(f"App exited {app.returncode}; see {log.name}")
    ws=windows()
    if len(ws)==1: ws[0].set_input_focus(X.RevertToParent,X.CurrentTime); d.sync()
    metadata={"ready":True,"pid":app.pid,"output":str(output),"running_binary_sha256":hashlib.file_digest(open(f"/proc/{app.pid}/exe","rb"),"sha256").hexdigest()}
    (output / "run-metadata.json").write_text(json.dumps(metadata,indent=2))
    print(json.dumps(metadata),flush=True)
    for line in sys.stdin:
        try: print(json.dumps(command(json.loads(line))),flush=True)
        except Exception as e: print(json.dumps({"error":str(e)}),flush=True)
        if app.poll() is not None: break
finally:
    if app.poll() is None:
        app.terminate()
        try: app.wait(timeout=5)
        except subprocess.TimeoutExpired: app.kill(); app.wait()
    d.close()
    if a11y.poll() is None:
        a11y.terminate()
        try: a11y.wait(timeout=3)
        except subprocess.TimeoutExpired: a11y.kill(); a11y.wait()
    log.close()
