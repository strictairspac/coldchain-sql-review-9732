/** @typedef {{id:number,name:string,description:string,original_sql:string}} Sample */
/** @typedef {{id:number,name:string,sample_id:number,candidate_sql:string,status:string}} Batch */
/** @typedef {{id:number,batch_id:number,result:Object}} Evidence */
/** @typedef {{id:number,name:string,idempotency_key:string,status:string,moves:Array<{from:number,to:number,state:string,note:string}>,deduplicated:boolean}} RenumberBatch */
export const entityNames={sample:'SQL 样本',batch:'复核批次',evidence:'执行证据',renumber:'调号批次'};
