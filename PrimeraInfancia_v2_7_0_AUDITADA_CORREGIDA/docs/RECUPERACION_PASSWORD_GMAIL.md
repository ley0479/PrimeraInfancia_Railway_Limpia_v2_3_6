# Recuperación de contraseña con Gmail SMTP

La plataforma usa `smtp.gmail.com` y lee toda credencial desde `.env`.

1. Activa la verificación en dos pasos de la cuenta Google.
2. Crea una **contraseña de aplicación** para Primera Infancia.
3. Configura `SMTP_USERNAME`, `SMTP_PASSWORD` y `PASSWORD_RESET_FROM_EMAIL` en `.env`.
4. Define `PASSWORD_RESET_PUBLIC_URL` con la URL desde la cual el usuario abrirá el enlace.
5. Reinicia la aplicación.

Nunca uses la contraseña normal de Gmail. No publiques ni confirmes el valor de `SMTP_PASSWORD` en logs, capturas o repositorios.
