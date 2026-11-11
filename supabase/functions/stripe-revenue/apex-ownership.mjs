/**
 * Fail-closed attribution for the shared RMC Stripe account.
 * Only signed live Stripe events from the verified APEX setup Payment Link or
 * an APEX-managed subscription invoice may be recorded as property 003.
 * Payment Link IDs are public object identifiers, not credentials. An unknown
 * link, a missing subscription metadata snapshot, or future checkout paths
 * remain unclassified until independently verified and reviewed.
 */
const APEX_SETUP_LINK_ID = 'plink_1U41IsPBIDRbWEMWwWHrFyko';
const APEX_PROPERTY_ID = '003';
const APEX_MANAGED_OFFER = 'ai_response_managed_monthly';

export function isApexRevenueEvent(event) {
  if (event?.livemode !== true) return false;
  const object = event?.data?.object;
  if (!object || typeof object !== 'object' || Array.isArray(object)) return false;

  if (
    event.type === 'checkout.session.completed' ||
    event.type === 'checkout.session.async_payment_succeeded'
  ) {
    return object.mode === 'payment' && object.payment_link === APEX_SETUP_LINK_ID;
  }

  if (event.type === 'invoice.paid') {
    // Stripe's invoice snapshot may be at the current parent path or the
    // legacy subscription_details path, depending on the webhook API version.
    const snapshots = [
      object.parent?.subscription_details?.metadata,
      object.subscription_details?.metadata,
    ];
    return snapshots.some((metadata) =>
      metadata?.apex_property_id === APEX_PROPERTY_ID &&
      metadata?.apex_offer === APEX_MANAGED_OFFER
    );
  }

  return false;
}
