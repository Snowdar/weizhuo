"""Single-window scene lifecycle, required by iOS 27 SDK. No backend patching."""
import sys
if sys.platform=='ios':
    from rubicon.objc import objc_method,objc_property,ObjCProtocol
    from toga_iOS.libs import UIResponder
    from toga_iOS.app import App
    def fit_safe_area():
        app=App.app.interface
        window=app.main_window
        inset=window._impl.native.safeAreaInsets
        top=max(0,inset.top-window._impl.container.top_offset)
        app.table.style.margin_top=top
        app.table.style.margin_bottom=0  # Let the scene reach the home indicator; web controls use safe-area inset.
        app.launcher.style.margin_top=top
        app.launcher.style.margin_bottom=inset.bottom
        app.fit_service_page()

    class WeizhuoSceneDelegate(UIResponder,protocols=[ObjCProtocol('UIWindowSceneDelegate')]):
        window=objc_property()
        @objc_method
        def scene_willConnectToSession_options_(self,scene,session,options)->None:
            window=App.app.interface.main_window
            self.window=window._impl.native
            self.window.windowScene=scene
            self.window.frame=scene.coordinateSpace.bounds
            self.window.makeKeyAndVisible()
            fit_safe_area()
            window.content.refresh()
        @objc_method
        def sceneDidBecomeActive_(self,scene)->None:
            App.app.interface.current_window.on_gain_focus()
        @objc_method
        def sceneWillResignActive_(self,scene)->None:
            App.app.interface.speaker.stop()
            App.app.interface.current_window.on_lose_focus()
        @objc_method
        def sceneDidEnterBackground_(self,scene)->None:
            App.app.interface.current_window.on_hide()
        @objc_method
        def sceneWillEnterForeground_(self,scene)->None:
            App.app.interface.current_window.on_show()
        @objc_method
        def windowScene_didUpdateCoordinateSpace_interfaceOrientation_traitCollection_(self,scene,space,orientation:int,traits)->None:
            window=App.app.interface.main_window
            window.on_resize()
            fit_safe_area()
            window.content.refresh()
