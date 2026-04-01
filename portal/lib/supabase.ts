import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

export type Client = {
  id: string
  name: string
  company: string
  email: string
  plan: string
  mrr: number
  due_day: number
  has_zenya: boolean
  has_trafego: boolean
  status: string
  created_at?: string
}
