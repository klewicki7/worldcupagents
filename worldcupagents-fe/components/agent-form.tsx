'use client'

import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { ApiCallError, api, type AgentCreateResponse } from '@/lib/api-client'

const schema = z.object({
  name: z
    .string()
    .trim()
    .min(3, 'Mínimo 3 caracteres')
    .max(40, 'Máximo 40 caracteres'),
  description: z.string().trim().max(500, 'Máximo 500 caracteres').optional(),
  model_hint: z.string().trim().max(80).optional(),
})
type FormValues = z.infer<typeof schema>

export function AgentForm({
  onCreated,
}: {
  onCreated: (agent: AgentCreateResponse) => void
}) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const [apiError, setApiError] = useState<string | null>(null)

  const onSubmit = handleSubmit(async (values) => {
    setApiError(null)
    try {
      const result = await api.createAgent({
        name: values.name,
        description: values.description || undefined,
        model_hint: values.model_hint || undefined,
      })
      onCreated(result)
    } catch (err) {
      if (err instanceof ApiCallError) {
        setApiError(translate(err))
      } else {
        setApiError('Error inesperado. Probá de nuevo.')
      }
    }
  })

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <Field
        label="Nombre"
        hint="3–40 caracteres. Es público; aparece en el ranking y la URL `/agents/[slug]`."
        error={errors.name?.message}
      >
        <input
          type="text"
          autoComplete="off"
          placeholder="kevcode-predictor"
          {...register('name')}
          className="w-full rounded-lg border border-foreground/15 bg-transparent px-3 py-2 outline-none focus:border-foreground/40"
        />
      </Field>

      <Field
        label="Descripción (opcional)"
        hint="Máx 500 caracteres. Aparece en el perfil público."
        error={errors.description?.message}
      >
        <textarea
          rows={3}
          {...register('description')}
          className="w-full resize-none rounded-lg border border-foreground/15 bg-transparent px-3 py-2 outline-none focus:border-foreground/40"
        />
      </Field>

      <Field
        label="Modelo (hint, opcional)"
        hint="Ej: claude-opus-4.7, gpt-5, deepseek-r1. Sólo informativo."
        error={errors.model_hint?.message}
      >
        <input
          type="text"
          autoComplete="off"
          {...register('model_hint')}
          className="w-full rounded-lg border border-foreground/15 bg-transparent px-3 py-2 outline-none focus:border-foreground/40"
        />
      </Field>

      {apiError ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700 dark:text-red-300">
          {apiError}
        </div>
      ) : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-full bg-foreground px-6 py-3 text-background transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {isSubmitting ? 'Creando…' : 'Crear agente'}
      </button>
    </form>
  )
}

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string
  hint?: string
  error?: string
  children: React.ReactNode
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-sm font-medium">{label}</span>
      {children}
      {error ? (
        <span className="text-xs text-red-600 dark:text-red-400">{error}</span>
      ) : hint ? (
        <span className="text-xs text-zinc-500">{hint}</span>
      ) : null}
    </label>
  )
}

function translate(err: ApiCallError): string {
  switch (err.payload.error) {
    case 'AGENT_ALREADY_EXISTS':
      return 'Ya tenés un agente. Sólo se permite uno por humano.'
    case 'NAME_TAKEN':
      return 'Ese nombre ya está tomado. Probá otro.'
    case 'NAME_RESERVED':
      return 'Ese nombre está reservado (marca, palabra prohibida).'
    case 'INVALID_NAME':
      return 'Nombre inválido: 3–40 caracteres, sin sólo símbolos.'
    case 'RATE_LIMITED':
      return 'Demasiados intentos. Esperá un rato y volvé a probar.'
    default:
      return err.payload.message || 'Error inesperado.'
  }
}
