import{listRenumberBatches}from'../api/renumber.js';export const renumbers={items:[],async load(){this.items=await listRenumberBatches();return this.items}};
