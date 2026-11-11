import { createClient } from "npm:@supabase/supabase-js@2.111.0";
import { createStripeRevenueHandler } from "./handler.mjs";

Deno.serve(createStripeRevenueHandler(createClient, Deno.env));
