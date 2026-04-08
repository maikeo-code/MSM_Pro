import api from './api';

export interface OrderOut {
  id: string;
  ml_order_id: string;
  listing_id: string | null;
  mlb_id: string;
  buyer_nickname: string;
  quantity: number;
  unit_price: number | string; // Backend retorna Decimal (string)
  total_amount: number | string; // Backend retorna Decimal (string)
  sale_fee: number | string; // Backend retorna Decimal (string)
  shipping_cost: number | string; // Backend retorna Decimal (string)
  net_amount: number | string; // Backend retorna Decimal (string)
  payment_status: string;
  shipping_status: string;
  order_date: string;
  payment_date: string | null;
  delivery_date: string | null;
}

export async function listOrders(period: string = "7d", mlAccountId?: string | null): Promise<OrderOut[]> {
  // Mapa de periodos para dias (backend usa period string)
  const periodMap: Record<string, string> = {
    "1d": "1d",
    "2d": "2d",
    "7d": "7d",
    "15d": "15d",
    "30d": "30d",
    "60d": "60d",
  };
  const finalPeriod = periodMap[period] ?? "7d";

  const params: Record<string, unknown> = { period: finalPeriod };
  if (mlAccountId) {
    params.ml_account_id = mlAccountId;
  }

  const { data } = await api.get<OrderOut[]>('/listings/orders/', {
    params,
  });

  // Converter Decimal strings para números
  return data.map((order) => ({
    ...order,
    unit_price: Number(order.unit_price),
    total_amount: Number(order.total_amount),
    sale_fee: Number(order.sale_fee),
    shipping_cost: Number(order.shipping_cost),
    net_amount: Number(order.net_amount),
  }));
}
