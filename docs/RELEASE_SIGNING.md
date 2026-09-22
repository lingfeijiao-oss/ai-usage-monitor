# Release Signing Boundary

CI build artifacts are release candidates until platform signing requirements
are completed.

## Windows

The current CI can create an Inno Setup installer, but the installer is not
Authenticode-signed unless a code-signing certificate is configured.

An unsigned installer may trigger Windows reputation / SmartScreen warnings.

## macOS

The current CI can create ARM64 and Intel `.app` / `.dmg` artifacts.

Public end-user distribution should add Apple Developer ID signing and Apple
notarization. Until those credentials and steps are configured, the DMGs are
unsigned release candidates rather than final public installers.

## Linux

The workflow creates an amd64 DEB and a portable tar.gz. Repository/package
signing can be added later if packages are distributed through a package
repository.

## CI safety

Signing credentials must be supplied through protected CI secrets. They must
never be committed to this repository.
