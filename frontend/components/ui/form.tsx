"use client"

import * as React from "react"
import type {
  Control,
  FieldPath,
  FieldValues,
  ControllerRenderProps,
} from "react-hook-form"
import { Controller, FormProvider, useFormContext } from "react-hook-form"

import { cn } from "@/lib/utils"
import { Label } from "@/components/ui/label"

function Form<TFieldValues extends FieldValues>({
  form,
  onSubmit,
  children,
  className,
}: {
  form: {
    handleSubmit: (cb: (values: TFieldValues) => any) => any
    control: Control<TFieldValues>
  }
  onSubmit: (values: TFieldValues) => any
  children: React.ReactNode
  className?: string
}) {
  return (
    <FormProvider {...(form as any)}>
      <form onSubmit={form.handleSubmit(onSubmit)} className={cn("space-y-6", className)}>
        {children}
      </form>
    </FormProvider>
  )
}

function FormField<TFieldValues extends FieldValues, TName extends FieldPath<TFieldValues>>({
  control,
  name,
  render,
}: {
  control: Control<TFieldValues>
  name: TName
  render: (props: { field: ControllerRenderProps<TFieldValues, TName> }) => React.ReactElement
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => render({ field })}
    />
  )
}

function FormItem({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("space-y-2", className)} {...props} />
}

function FormLabel({ className, ...props }: React.ComponentProps<"label">) {
  return <Label className={cn("text-sm", className)} {...props} />
}

function FormControl({ children }: { children: React.ReactElement }) {
  return children
}

function getNestedErrorMessage(errors: unknown, name: string): string | undefined {
  const parts = name.split(".")
  let cur: unknown = errors
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return undefined
    cur = (cur as Record<string, unknown>)[p]
  }
  if (cur && typeof cur === "object" && "message" in cur) {
    const msg = (cur as { message?: unknown }).message
    return msg != null ? String(msg) : undefined
  }
  return undefined
}

function FormMessage({ name }: { name: string }) {
  const { formState } = useFormContext()
  const err = getNestedErrorMessage(formState.errors, name)
  if (!err) return null

  return <p className="text-sm text-destructive">{err}</p>
}

export { Form, FormField, FormItem, FormLabel, FormControl, FormMessage }

