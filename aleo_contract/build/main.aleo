program aleo_contract_fixed.aleo;

function prove_badges:
    input r0 as u8.private;
    gte r0 3u8 into r1;
    output r1 as boolean.private;

function verify_age:
    input r0 as u8.private;
    gte r0 12u8 into r1;
    output r1 as boolean.private;
