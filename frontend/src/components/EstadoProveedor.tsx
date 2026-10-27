import type { Health } from "../lib/contracts";
import { Icono } from "./Icono";

type Configuracion = NonNullable<Health["provider_configuration"]>;

export function EstadoProveedor({ configuracion }: { configuracion?: Configuracion }) {
  if (!configuracion) return null;
  const etiquetas = {
    configured: "Proveedor preparado",
    offline: "Modo local",
    not_configured: "Sin configurar",
  };
  return <span className={`proveedor-pill ${configuracion.status}`}
    title={configuracion.status === "configured"
      ? "Configuración presente. Credencial, saldo y conectividad sin verificar."
      : configuracion.message}>
    <span className="proveedor-luz" aria-hidden="true" />
    {etiquetas[configuracion.status]}
  </span>;
}

export function AvisoProveedor({ configuracion }: { configuracion?: Configuracion }) {
  if (configuracion?.status !== "not_configured") return null;
  return <section className="aviso-proveedor" role="status">
    <span className="aviso-proveedor-icono" aria-hidden="true"><Icono nombre="seguridad" /></span>
    <div className="aviso-proveedor-contenido">
      <strong>Proveedor de IA no configurado</strong>
      <p>Tu espacio local sigue disponible. Completa la configuración para activar los agentes con modelo.</p>
      <div className="proveedor-campos" aria-label="Configuración pendiente">
        {configuracion.missing_fields.map(campo => <code key={campo}>{campo}</code>)}
      </div>
    </div>
    <div className="proveedor-ruta"><span>Configuración de Windows</span>
      <code>%LOCALAPPDATA%/AISWESystem/config/.env</code>
      <span>Guarda los cambios y vuelve a abrir la aplicación.</span>
    </div>
  </section>;
}
