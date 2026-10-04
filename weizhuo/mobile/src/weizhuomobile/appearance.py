"""Platform adapters for the hall's ivory, emerald and brass visual tokens."""
import sys
from importlib.resources import files
BG='#f1f3eb'
PANEL='#fffef9'
TEXT='#335540'
MUTED='#647c72'
SECONDARY='#edf3e8'
BORDER='#ccd9c8'
GOLD='#deb777'
GOLD_TEXT='#3c3925'


def style_native_controls(buttons,field,card):
    if sys.platform!='ios':return
    from toga_iOS.colors import native_color
    from toga.colors import color
    from toga_iOS.libs import UIView
    for button in buttons:
        layer=button._impl.native.layer
        layer.cornerRadius=9
        layer.borderWidth=1
        layer.borderColor=native_color(color(BORDER)).CGColor
        button._impl.native.clipsToBounds=True
    native=field._impl.native
    from rubicon.objc import ObjCClass,SEL
    toolbar=ObjCClass('UIToolbar').alloc().init()
    toolbar.sizeToFit()
    spacer=ObjCClass('UIBarButtonItem').alloc().initWithBarButtonSystemItem(5,target=None,action=None)
    done=ObjCClass('UIBarButtonItem').alloc().initWithTitle('完成',style=2,target=native,action=SEL('resignFirstResponder'))
    toolbar.items=[spacer,done]
    native.inputAccessoryView=toolbar
    native.borderStyle=0
    native.layer.cornerRadius=9
    native.layer.borderWidth=1
    native.layer.borderColor=native_color(color(BORDER)).CGColor
    native.clipsToBounds=True
    # Plain UITextField has no text inset; reserve the hall's input padding.
    from rubicon.objc import NSRect,NSPoint,NSSize
    pad=UIView.alloc().initWithFrame(NSRect(NSPoint(0,0),NSSize(12,1)))
    native.leftView=pad
    native.leftViewMode=3
    card._impl.native.layer.cornerRadius=17
    card._impl.native.layer.borderWidth=1
    card._impl.native.layer.borderColor=native_color(color('#d2dfd6')).CGColor
    card._impl.native.clipsToBounds=True


def install_background(window):
    if sys.platform!='ios':return None
    from toga_iOS.libs import UIImage,UIImageView
    native=window._impl.container.native
    image=UIImage.imageWithContentsOfFile(str(files('weizhuomobile.runtime')/'resources/service-background.jpg'))
    view=UIImageView.alloc().initWithImage(image)
    view.frame=native.bounds
    view.autoresizingMask=18  # Flexible width and height, including rotation.
    view.contentMode=2  # Aspect fill; artwork keeps the center quiet.
    view.clipsToBounds=True
    native.insertSubview(view,atIndex=0)
    return view


def configure_webview(web):
    """Keep document scrolling, remove native bounce and automatic inset layering."""
    if sys.platform != 'ios':return
    native = web._impl.native
    native.clipsToBounds = True
    scroll = native.scrollView
    scroll.bounces = False
    scroll.alwaysBounceVertical = False
    scroll.alwaysBounceHorizontal = False
    scroll.contentInsetAdjustmentBehavior = 2  # Never: project root already fits safe area.
    try:
        from rubicon.objc import ObjCClass
        ObjCClass('WZKeyboardTracker').sharedTracker().webView=native
    except NameError:pass
    scroll.keyboardDismissMode = 0  # Do not let a scroll gesture silently dismiss editing.


def fit_fullscreen_web(window, web):
    """Override only the WebView bounds after Toga layout; leave root and service UI intact."""
    if sys.platform != 'ios' or web._impl.container is None:return
    bounds = window._impl.container.native.bounds
    web._impl.constraints.update(0, 0, bounds.size.width, bounds.size.height)


def web_safe_area(window):
    if sys.platform != 'ios':return dict(top=0,bottom=0,left=0,right=0)
    area=window._impl.native.safeAreaInsets
    return {key:float(getattr(area,key)) for key in ('top','bottom','left','right')}


def web_keyboard_state(web):
    if sys.platform!='ios':return {}
    from rubicon.objc import ObjCClass
    import json
    try:
        tracker=ObjCClass('WZKeyboardTracker').sharedTracker()
        tracker.webView=web._impl.native
        return json.loads(str(tracker.stateJSON()))
    except (NameError,ValueError):return {}


def lock_table_scroll(web, locked):
    """Freeze only WKWebView's outer viewport; keep local DOM scrolling available."""
    if sys.platform != 'ios':return
    native = web._impl.native
    native.scrollView.scrollEnabled = not locked
    from rubicon.objc import ObjCClass
    try:
        tracker = ObjCClass('WZKeyboardTracker').sharedTracker()
        tracker.webView = native
        tracker.tableLocked = bool(locked)
    except NameError:pass  # System-only builds may lack the optional native bridge.
