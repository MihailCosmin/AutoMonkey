# Flutter: widget tests, goldens and integration_test

Layer 1 of UI testing for Flutter desktop apps (Windows, Linux, macOS). It covers widget-level behavior, golden rendering, and integration tests that drive the real app build inside the Flutter test harness.

It cannot do:
- Real OS input (mouse, keyboard, touch) at the OS level.
- The native window, native dialogs, or file pickers.
- DPI scaling on the user's display.
- Real fonts unless you load them.

That is AutoMonkey's job (layer 2). Use AutoMonkey for anything that needs the real OS.

## Widget tests

Widget tests run fast, headless, and in-process. They pump a widget tree and simulate gestures and input through the `tester` API.

```dart
testWidgets('save button shows confirmation', (tester) async {
  await tester.pumpWidget(MaterialApp(home: MyPage()));
  await tester.tap(find.text('Save'));
  await tester.pumpAndSettle();
  expect(find.text('Saved'), findsOneWidget);
});
```

Common tester actions:
- `tester.enterText(find.byType(TextField), 'abc')` - type into a text field.
- `tester.sendKeyEvent(LogicalKeyboardKey.tab)` - send a single key event.
- `tester.drag(find.byKey(Key('item0')), Offset(0, 200))` - drag by an offset.
- Keyboard shortcuts: hold a modifier with `sendKeyDownEvent`, then `sendKeyUpEvent`:

```dart
await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
await tester.sendKeyEvent(LogicalKeyboardKey.keyS);
await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
```

Use `pump()` for a single frame and `pumpAndSettle()` when animations must finish. Prefer `find.byKey` with stable keys over text when text changes.

## Goldens

Golden tests compare a rendered widget against a stored PNG.

```dart
await expectLater(find.byType(MyPage), matchesGoldenFile('goldens/my_page.png'));
```

To accept new or changed output:

```
flutter test --update-goldens
```

Set a fixed surface size so goldens are stable:

```dart
tester.view.physicalSize = const Size(1280, 800);
tester.view.devicePixelRatio = 1.0;
addTearDown(tester.view.reset);
```

Fonts render as boxes (Ahem) unless real fonts are loaded. Load them with `FontLoader` or use packages like `golden_toolkit` or `alchemist`.

Goldens differ per OS. Generate them on the same OS the CI uses, and store them per OS if you test on more than one.

## integration_test

`integration_test` runs the real app build inside the test harness. Add it to `pubspec.yaml`:

```yaml
dev_dependencies:
  integration_test:
    sdk: flutter
```

File `integration_test/app_test.dart`:

```dart
final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
```

Run on the desktop:

```
flutter test integration_test -d windows
```

or `-d linux` / `-d macos`.

It drives the real app build, but still not real OS input. It cannot click outside the Flutter window or interact with native dialogs.

## Accessibility

Flutter desktop exposes a semantics tree to the OS (UI Automation on Windows). Give widgets `Semantics` labels and tooltips so AutoMonkey's `controls` / `click_control` can find them (icon-only buttons without a label are invisible to it).

`SemanticsDebugger` helps: enable it to see the semantics tree overlaid on the app.

Test semantics in widget tests:

```dart
expect(
  tester.getSemantics(find.text('Save')),
  matchesSemantics(label: 'Save', isButton: true),
);
```

## Checklist

- Every route/page reachable.
- Every button, menu, and keyboard shortcut.
- Dialogs (open, confirm, cancel).
- Form validation (empty, invalid, valid).
- Long text overflow. RenderFlex overflow errors fail tests - good.
- Light and dark goldens.
- Text scale 1.0 and 1.5:

```dart
tester.platformDispatcher.textScaleFactorTestValue = 1.5;
addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
```

(Newer Flutter versions move text scaling to `TextScaler`; if the call above is reported
as deprecated, wrap the widget in `MediaQuery(data: MediaQueryData(textScaler:
TextScaler.linear(1.5)), child: ..)` instead.)

## CI

Run widget and golden tests:

```
flutter test
```

Run integration tests on a runner with a display:

```
flutter test integration_test -d <os>
```

On Linux CI without a display, use `xvfb-run`:

```
xvfb-run flutter test integration_test -d linux
```
