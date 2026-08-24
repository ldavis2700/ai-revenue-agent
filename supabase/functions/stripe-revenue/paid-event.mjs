/**
 * Normalize Stripe events that represent newly collected revenue.
 *
 * Subscription Checkout emits both checkout.session.completed and invoice.paid
 * for the initial charge. We count subscription revenue only from invoice.paid
 * so the initial payment is not recorded twice.
 */
export function paidEvent(event) {
  const object = event?.data?.object ?? {};

  const checkoutSucceeded =
    event?.type === "checkout.session.completed" ||
    event?.type === "checkout.session.async_payment_succeeded";

  if (
    checkoutSucceeded &&
    object.mode === "payment" &&
    object.payment_status === "paid"
  ) {
    return {
      amount: Number(object.amount_total ?? 0),
      currency: String(object.currency ?? "usd").toUpperCase(),
      email: String(
        object.customer_details?.email ?? object.customer_email ?? "",
      ).trim().toLowerCase(),
      paymentReference: String(object.payment_intent ?? object.id ?? ""),
      kind: "one_time_checkout",
    };
  }

  const subscription =
    object.subscription ?? object.parent?.subscription_details?.subscription;

  if (event?.type === "invoice.paid" && subscription) {
    const invoicePaymentIntent =
      object.payment_intent ??
      object.payments?.data?.[0]?.payment?.payment_intent;

    return {
      amount: Number(object.amount_paid ?? 0),
      currency: String(object.currency ?? "usd").toUpperCase(),
      email: String(object.customer_email ?? "").trim().toLowerCase(),
      paymentReference: String(invoicePaymentIntent ?? object.id ?? ""),
      kind: "subscription_invoice",
    };
  }

  return null;
}
