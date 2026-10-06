You are segmenting a screen recording of a moderated usability-test session (video call with a shared screen) into a timeline of WHAT IS ON THE SHARED SCREEN.

This clip covers {{window_start}}–{{window_end}} of the full recording. Report all times as MM:SS in FULL-recording time.

The client's surfaces are: {{client_surfaces}}

Produce consecutive intervals that cover the whole clip with no gaps and no overlaps. Start a new interval whenever the kind of surface or the main view on the shared screen changes (e.g. landing page → privacy page, dashboard → settings dialog, app → video-call window). Ignore pointer movement and scrolling within the same view.

For each interval:
- t_start / t_end (MM:SS).
- surface: one of
  client_web (a client website page), client_app (the client's application), client_docs (client documentation/legal pages),
  whiteboard (FigJam/Miro/boards), video_call (the call window itself), file_storage (Drive, file manager, downloads),
  os_desktop (desktop, system dialogs, settings), other_web (any other website), not_shared (no shared screen / camera tiles only).
- address: the domain or URL shown in the address bar, or the window title, exactly as visible; empty if not legible.
- view: a short name of what is shown (e.g. "landing page hero", "Get started card", "Settings › Data", "persona cards").
- confidence: high, medium or low.

Rules: only what you can see; if the shared screen is not visible, use not_shared. Do not describe user intent.

notes: anything that limits the segmentation (screen share stopped, blurred frames …).
