import api from './api';

export interface OrderOut {
  id: string;
  ml_order_id: string;
  listing_id: string | null;
  mlb_id: string;
  buyer_nickname: string;
  quantity: number;
  unit_price: number;
  total_amount: number;
  sale_fee: number;
  shipping_cost: number;
  net_amount: number;
  payment_status: string;
  shipping_status: string;
  order_date: string;
  payment_date: string | null;
  delivery_date: string | null;
}

export async function listOrders(): Promise<OrderOut[]> {
  const { data } = await api.get('/listings/orders/');
  return data;
}
